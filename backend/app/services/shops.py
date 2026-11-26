"""Do'konlar: har foydalanuvchi (masalan, kanal egasi) o'z havolasi bilan donat do'koni ochadi.

- Havola `t.me/bot?start=shop_<slug>`: bosgan odam shu do'konga BIRIKADI (birinchi marta bosgan do'kon, keyin o'zgarmaydi).
- Birikkan odamning har bir bajarilgan buyurtmasidan do'kon egasiga komissiya hamyonga avtomatik tushadi.
- Daraja (Bronza → Brilliant) kelgan savdo summasiga qarab oshadi, komissiya foizi ham oshadi (admin Sozlamalarda o'zgartiradi).
- O'z-o'ziga xarid va bir buyurtmadan ikki marta komissiya bo'lmaydi (idempotent kalit).
"""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, BadState, NotFound
from app.models import Shop, ShopSale, User
from app.services import app_settings, wallet

LEVELS = [("bronze", "Bronza", "🥉"), ("silver", "Kumush", "🥈"), ("gold", "Oltin", "🥇"), ("diamond", "Brilliant", "💎")]
RESERVED = {"admin", "vaynexo", "support", "bot", "shop", "test", "null", "none", "api", "wallet", "arena"}
SLUG_RE = re.compile(r"^[a-z0-9_]{3,24}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def clean_slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_]", "", (s or "").strip().lower().lstrip("@"))[:24]


async def enabled(session: AsyncSession) -> bool:
    return await app_settings.get_value(session, "shop_on") == "on"


async def level_info(session: AsyncSession, sales_total: int) -> dict:
    """Daraja, komissiya foizi va keyingi darajagacha qolgan summa."""
    s = await app_settings.get_many(session, "shop_pct_1", "shop_pct_2", "shop_pct_3", "shop_pct_4", "shop_th_2", "shop_th_3", "shop_th_4")
    pcts = [int(s[f"shop_pct_{i}"]) for i in range(1, 5)]
    ths = [0, int(s["shop_th_2"]), int(s["shop_th_3"]), int(s["shop_th_4"])]
    idx = max(i for i, th in enumerate(ths) if sales_total >= th)
    nxt = idx + 1 if idx < 3 else None
    key, name, icon = LEVELS[idx]
    return {"level": idx + 1, "key": key, "name": name, "icon": icon, "pct": pcts[idx],
            "next": {"name": LEVELS[nxt][1], "icon": LEVELS[nxt][2], "pct": pcts[nxt], "need": ths[nxt] - sales_total, "at": ths[nxt]} if nxt is not None else None,
            "from": ths[idx]}


async def create(session: AsyncSession, user_id: int, slug: str, name: str, tagline: str) -> Shop:
    if not await enabled(session):
        raise BadState("Do'konlar hozircha yopiq")
    slug = clean_slug(slug)
    if not SLUG_RE.match(slug) or slug in RESERVED:
        raise AppError("bad_slug", "Havola nomi: 3–24 ta kichik lotin harf, raqam yoki _")
    if await session.scalar(select(Shop.id).where(Shop.owner_id == user_id)):
        raise BadState("Sizda do'kon allaqachon bor")
    if await session.scalar(select(Shop.id).where(Shop.slug == slug)):
        raise BadState("Bu nom band, boshqasini tanlang")
    name = (name or "").strip()[:48]
    if len(name) < 2:
        raise AppError("bad_name", "Do'kon nomini kiriting")
    shop = Shop(owner_id=user_id, slug=slug, name=name, tagline=(tagline or "").strip()[:120])
    session.add(shop)
    await session.flush()
    return shop


async def update(session: AsyncSession, user_id: int, name: str | None, tagline: str | None) -> Shop:
    shop = await session.scalar(select(Shop).where(Shop.owner_id == user_id))
    if shop is None:
        raise NotFound("Do'kon")
    if name is not None:
        if len((name or "").strip()) < 2:
            raise AppError("bad_name", "Do'kon nomini kiriting")
        shop.name = name.strip()[:48]
    if tagline is not None:
        shop.tagline = tagline.strip()[:120]
    return shop


async def attach(session: AsyncSession, user: User, slug: str) -> Shop | None:
    """Foydalanuvchini do'konga biriktiradi (faqat bir marta; o'z do'koniga emas)."""
    if user.shop_id or not await enabled(session):
        return None
    shop = await session.scalar(select(Shop).where(Shop.slug == clean_slug(slug), Shop.active.is_(True)))
    if shop is None or shop.owner_id == user.id:
        return None
    user.shop_id = shop.id
    return shop


async def sales_total(session: AsyncSession, shop_id: int) -> int:
    return int(await session.scalar(select(func.coalesce(func.sum(ShopSale.amount), 0)).where(ShopSale.shop_id == shop_id, ShopSale.status == "paid")) or 0)


async def on_sale(session: AsyncSession, buyer_id: int, kind: str, order_id: int, amount: int) -> ShopSale | None:
    """Buyurtma bajarilganda chaqiriladi: biriktirilgan do'kon egasiga komissiya. Qayta chaqirsa ham ikki marta bermaydi."""
    buyer = await session.get(User, buyer_id)
    if buyer is None or not buyer.shop_id or amount <= 0:
        return None
    shop = await session.get(Shop, buyer.shop_id)
    if shop is None or not shop.active or shop.owner_id == buyer_id or not await enabled(session):
        return None
    if await session.scalar(select(ShopSale.id).where(ShopSale.kind == kind, ShopSale.order_id == order_id)):
        return None
    info = await level_info(session, await sales_total(session, shop.id))  # daraja shu buyurtmadan OLDINGI savdo bo'yicha
    commission = amount * info["pct"] // 100
    sale = ShopSale(shop_id=shop.id, buyer_id=buyer_id, kind=kind, order_id=order_id, amount=amount, commission=commission, pct=info["pct"], status="paid")
    session.add(sale)
    await session.flush()
    if commission > 0:
        await wallet.credit(session, shop.owner_id, commission, "shop_commission", f"shop_sale:{kind}:{order_id}", ref_type="shop", ref_id=shop.id)
    return sale


async def overview(session: AsyncSession, user: User, bot_username: str) -> dict:
    shop = await session.scalar(select(Shop).where(Shop.owner_id == user.id))
    if shop is None:
        return {"shop": None, "enabled": await enabled(session), "levels": await levels_table(session)}
    total = await sales_total(session, shop.id)
    info = await level_info(session, total)
    week_ago, today = _now() - timedelta(days=7), _now().replace(hour=0, minute=0, second=0, microsecond=0)
    base = select(func.coalesce(func.sum(ShopSale.commission), 0), func.count(), func.coalesce(func.sum(ShopSale.amount), 0)).where(
        ShopSale.shop_id == shop.id, ShopSale.status == "paid")
    earned, orders, _ = (await session.execute(base)).one()
    e_week, o_week, _ = (await session.execute(base.where(ShopSale.created_at >= week_ago))).one()
    e_day, o_day, _ = (await session.execute(base.where(ShopSale.created_at >= today))).one()
    customers = int(await session.scalar(select(func.count()).select_from(User).where(User.shop_id == shop.id)) or 0)
    buyers = int(await session.scalar(select(func.count(func.distinct(ShopSale.buyer_id))).where(ShopSale.shop_id == shop.id)) or 0)
    rank = 1 + int(await session.scalar(select(func.count()).select_from(
        select(ShopSale.shop_id).where(ShopSale.status == "paid").group_by(ShopSale.shop_id).having(func.sum(ShopSale.amount) > total).subquery())) or 0)
    return {
        "enabled": await enabled(session), "levels": await levels_table(session),
        "shop": {"slug": shop.slug, "name": shop.name, "tagline": shop.tagline, "active": shop.active,
                 "link": f"https://t.me/{bot_username}?start=shop_{shop.slug}" if bot_username else None},
        "level": info, "sales_total": total,
        "stats": {"customers": customers, "buyers": buyers, "orders": int(orders), "earned": int(earned),
                  "week": {"orders": int(o_week), "earned": int(e_week)}, "today": {"orders": int(o_day), "earned": int(e_day)}},
        "rank": rank,
    }


async def levels_table(session: AsyncSession) -> list[dict]:
    s = await app_settings.get_many(session, "shop_pct_1", "shop_pct_2", "shop_pct_3", "shop_pct_4", "shop_th_2", "shop_th_3", "shop_th_4")
    ths = [0, int(s["shop_th_2"]), int(s["shop_th_3"]), int(s["shop_th_4"])]
    return [{"name": n, "icon": ic, "pct": int(s[f"shop_pct_{i + 1}"]), "from": ths[i]} for i, (_, n, ic) in enumerate(LEVELS)]


async def top(session: AsyncSession, days: int = 30, limit: int = 10) -> list[dict]:
    since = _now() - timedelta(days=days)
    rows = (await session.execute(
        select(Shop, func.sum(ShopSale.amount).label("s"), func.count().label("n"))
        .join(ShopSale, ShopSale.shop_id == Shop.id)
        .where(ShopSale.status == "paid", ShopSale.created_at >= since, Shop.active.is_(True))
        .group_by(Shop.id).order_by(func.sum(ShopSale.amount).desc()).limit(limit))).all()
    out = []
    for i, (shop, s, n) in enumerate(rows):
        info = await level_info(session, await sales_total(session, shop.id))
        out.append({"place": i + 1, "name": shop.name, "slug": shop.slug, "icon": info["icon"], "level": info["name"], "orders": int(n), "sales": int(s or 0)})
    return out
