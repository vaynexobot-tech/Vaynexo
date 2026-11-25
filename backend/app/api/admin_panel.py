"""Yangi admin panel API: bosh sahifa (bugungi tushum, API balanslari, «hozir bajarish kerak»), yagona buyurtmalar ro'yxati
va katalog (o'yinlar tartibi, bir o'yinda bir nechta API, narx taqqoslash va almashtirish).

Eski bo'limlar (/admin/withdrawals, /admin/donate, ...) o'zgarmaydi — bu yerdagi amallar o'sha xizmatlarni chaqiradi.
"""

import re
import statistics
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update

from app.api.deps import AdminUser, SessionDep
from app.api.donate import invalidate_packages_cache
from app.config import settings
from app.errors import AppError, BadState, NotFound
from app.models import (
    BoostOrder, Deal, DonateGame, DonateOrder, DonatePackage, DonateProvider, IncomingPayment, Listing, PartnerVideo, Rental,
    RentListing, TgOrder, Topup, User, Withdrawal,
)
from app.queue import enqueue
from app.services import app_settings, donate_catalog, launch, p2p
from app.services import donate as donate_svc
from app.services import services as svc
from app.services.notify import Outbox
from app.services.reports import TZ

router = APIRouter(prefix="/admin", tags=["admin"])

ATTENTION_AFTER = timedelta(minutes=10)  # shuncha vaqtdan beri «jarayonda» — diqqat talab qiladi
_inline: list = [None, 0.0]  # BotFather'da inline rejim yoqilganmi (getMe), 1 soat kesh


def _day(days_ago: int = 0) -> datetime:
    d = datetime.now(TZ).date() - timedelta(days=days_ago)
    return datetime.combine(d, datetime.min.time(), TZ).astimezone(timezone.utc)


def _dec(v) -> Decimal | None:
    try:
        return Decimal(str(v)) if v not in (None, "") else None
    except (InvalidOperation, ValueError):
        return None


def _uname(u: User | None) -> str:
    if u is None:
        return "—"
    return f"@{u.username}" if u.username else (u.first_name or str(u.id))


async def _users(session, ids) -> dict[int, User]:
    ids = {i for i in ids if i}
    if not ids:
        return {}
    return {u.id: u for u in await session.scalars(select(User).where(User.id.in_(ids)))}


async def _inline_enabled() -> bool | None:
    if time.monotonic() - _inline[1] < 3600 and _inline[1]:
        return _inline[0]
    try:
        from app.bot.instance import get_bot

        me = await get_bot().get_me()
        _inline[:] = [bool(me.supports_inline_queries), time.monotonic()]
    except Exception:  # noqa: BLE001 — token yo'q (test) yoki Telegram javob bermadi
        return None
    return _inline[0]


# ------------------------------------------------------------------ bosh sahifa
async def _sales(session, since: datetime, until: datetime | None = None) -> int:
    total = 0
    for model, col in ((DonateOrder, DonateOrder.price), (TgOrder, TgOrder.price), (BoostOrder, BoostOrder.price)):
        q = select(func.coalesce(func.sum(col), 0)).where(model.status == "done", model.created_at >= since)
        if until is not None:
            q = q.where(model.created_at < until)
        total += int(await session.scalar(q) or 0)
    return total


async def _queue(session) -> list[dict]:
    items: list[dict] = []
    wd = list(await session.scalars(select(Withdrawal).where(Withdrawal.status == "pending").order_by(Withdrawal.id).limit(6)))
    tp = list(await session.scalars(select(Topup).where(Topup.status == "checking").order_by(Topup.claimed_at).limit(6)))
    tg = list(await session.scalars(select(TgOrder).where(TgOrder.status == "processing").order_by(TgOrder.id).limit(20)))
    dn = list(await session.scalars(select(DonateOrder).where(DonateOrder.status == "review").order_by(DonateOrder.id).limit(6)))
    users = await _users(session, [x.user_id for x in (*wd, *tp, *tg, *dn)])
    for t in tp:
        items.append({"kind": "topup", "id": t.id, "title": f"Kirim · {t.pay_amount:,} so'm".replace(",", " "), "amount": t.pay_amount,
                      "sub": f"{_uname(users.get(t.user_id))} · karta ••{t.card_last4 or '—'}" + (" · chek bor" if t.has_receipt else ""),
                      "at": (t.claimed_at or t.created_at).isoformat() if (t.claimed_at or t.created_at) else None,
                      "actions": [["confirm", "Tasdiqlash", "ok"], ["reject", "Rad etish", "no"]]})
    for w in wd:
        items.append({"kind": "withdraw", "id": w.id, "title": f"Pul yechish · {w.amount:,} so'm".replace(",", " "), "amount": w.amount,
                      "sub": f"{_uname(users.get(w.user_id))} · {w.card_number[:4]} •• {w.card_number[-4:]}", "copy": w.card_number,
                      "at": w.created_at.isoformat() if w.created_at else None,
                      "actions": [["paid", "To'landi", "ok"], ["reject", "Rad etish", "no"]]})
    for o in tg:
        auto = (o.details or {}).get("auto") or {}
        if o.kind in ("premium", "stars") and not auto.get("manual") and datetime.now(timezone.utc) - o.created_at < ATTENTION_AFTER:
            continue  # avtomatik bajarilyapti
        items.append({"kind": "tg", "id": o.id, "title": f"{o.title} → @{o.target_username.lstrip('@')}", "amount": o.price,
                      "sub": f"{_uname(users.get(o.user_id))} · " + (auto.get("why") or "qo'lda bajariladi"),
                      "at": o.created_at.isoformat() if o.created_at else None,
                      "actions": [["done", "Bajarildi", "ok"], ["refund", "Pulni qaytarish", "no"]]})
    for o in dn:
        items.append({"kind": "donate", "id": o.id, "title": f"{o.title}", "amount": o.price, "game": o.game,
                      "sub": f"ID {o.player_id}" + (f" ({o.zone_id})" if o.zone_id else "") + f" · {_uname(users.get(o.user_id))}",
                      "error": o.error, "at": o.created_at.isoformat() if o.created_at else None,
                      "actions": [["retry", "Qayta", "y"], ["done", "Qo'lda bajarildi", "ok"], ["refund", "Qaytarish", "no"]]})
    items.sort(key=lambda x: x["at"] or "")
    return items[:12]


async def _links(session) -> list[dict]:
    q = [
        ("incoming", "Bog'lanmagan kirimlar", select(func.count()).select_from(IncomingPayment).where(IncomingPayment.status == "unmatched")),
        ("moderation", "E'lonlar tekshiruvi", select(func.count()).select_from(Listing).where(Listing.status == "moderation")),
        ("disputes", "Nizolar", select(func.count()).select_from(Deal).where(Deal.status == "disputed")),
        ("rent", "Ijara", select(func.count()).select_from(RentListing).where(RentListing.status == "moderation")),
        ("rent", "Ijara nizolari", select(func.count()).select_from(Rental).where(Rental.status == "disputed")),
        ("boost", "Boost buyurtmalar", select(func.count()).select_from(BoostOrder).where(BoostOrder.status.in_(("searching", "disputed")))),
        ("kyc", "Identifikatsiya", select(func.count()).select_from(User).where(User.kyc_status == "pending")),
        ("partner", "Hamkor videolari", select(func.count()).select_from(PartnerVideo).where(PartnerVideo.status == "pending")),
    ]
    out = []
    for sec, label, stmt in q:
        n = int(await session.scalar(stmt) or 0)
        if n:
            out.append({"section": sec, "label": label, "count": n})
    return out


@router.get("/dashboard")
async def dashboard(admin: AdminUser, session: SessionDep):
    t0, y0 = _day(0), _day(1)
    rate = int(await app_settings.get_value(session, "donate_usd_rate"))
    today, yday = await _sales(session, t0), await _sales(session, y0, t0)
    rows = (await session.execute(select(DonateOrder.price, DonatePackage.cost_usd).join(DonatePackage, DonatePackage.id == DonateOrder.package_id)
                                  .where(DonateOrder.status == "done", DonateOrder.created_at >= t0))).all()
    profit = sum(int(p - c * rate) for p, c in ((p, _dec(c)) for p, c in rows) if c is not None)
    orders = int(await session.scalar(select(func.count()).select_from(DonateOrder).where(DonateOrder.created_at >= t0)) or 0)
    orders += int(await session.scalar(select(func.count()).select_from(TgOrder).where(TgOrder.created_at >= t0)) or 0)
    provs = []
    for p in await session.scalars(select(DonateProvider).order_by(DonateProvider.id)):
        bal = _dec(p.balance_usd)
        provs.append({"id": p.id, "name": p.name, "kind": p.kind, "is_active": p.is_active, "balance_usd": p.balance_usd,
                      "low": bal is not None and bal < Decimal(str(settings.donate_low_balance_usd)), "error": p.last_error})
    week = (await session.execute(select(DonateOrder.game, func.count()).where(DonateOrder.status == "done", DonateOrder.created_at >= _day(6))
                                  .group_by(DonateOrder.game).order_by(func.count().desc()).limit(5))).all()
    total_w = sum(n for _, n in week) or 1
    names = {g.slug: g.name for g in await session.scalars(select(DonateGame).where(DonateGame.slug.in_([g for g, _ in week] or [""])))}
    return {
        "today": {"sales": today, "yesterday": yday, "profit": profit, "orders": orders,
                  "new_users": int(await session.scalar(select(func.count()).select_from(User).where(User.created_at >= t0)) or 0),
                  "users": int(await session.scalar(select(func.count()).select_from(User)) or 0)},
        "providers": provs,
        "bot": {"open": await launch.is_open(), "guests": len(await launch.guests()), "inline": await _inline_enabled()},
        "queue": await _queue(session),
        "links": await _links(session),
        "top_games": [{"game": g, "name": names.get(g, g), "share": round(n * 100 / total_w)} for g, n in week],
    }


class ActIn(BaseModel):
    action: str = Field(max_length=16)
    note: str = Field("", max_length=300)


@router.post("/queue/{kind}/{item_id}")
async def queue_action(kind: str, item_id: int, body: ActIn, admin: AdminUser, session: SessionDep):
    """Bosh sahifadagi tugmalar: mavjud xizmatlar orqali bajariladi (audit va xabarlar o'sha yerda)."""
    out = Outbox()
    if kind == "donate" and body.action == "retry":
        async with session.begin():
            o = await session.get(DonateOrder, item_id)
            if o is None or o.status != "review":
                raise BadState("Faqat tekshiruvdagi buyurtmani qayta yuborish mumkin")
            o.status, o.attempts = "processing", 0
        await enqueue("fulfil_donate", item_id, "check")
        return {"ok": True}
    async with session.begin():
        if kind == "withdraw" and body.action in ("paid", "reject"):
            await svc.resolve_withdrawal(session, item_id, body.action, body.note, out)
        elif kind == "topup" and body.action == "confirm":
            await p2p.admin_confirm(session, item_id, out)
        elif kind == "topup" and body.action == "reject":
            await p2p.admin_reject(session, item_id, body.note or None, out)
        elif kind == "tg" and body.action in ("done", "refund"):
            await svc.resolve_tg_order(session, item_id, body.action, body.note, out)
        elif kind == "donate" and body.action in ("done", "refund"):
            await donate_svc.admin_resolve(session, item_id, body.action, out)
        else:
            raise AppError("bad_action", "Noma'lum amal")
    await out.flush()
    return {"ok": True}


# ------------------------------------------------------------------ yagona buyurtmalar
DONATE_ST = {"done": ("Yetkazildi", "g"), "refunded": ("Qaytarildi", "m"), "review": ("Tekshiruv", "r"), "processing": ("Jarayonda", "y")}
TG_ST = {"done": ("Bajarildi", "g"), "refunded": ("Qaytarildi", "m"), "processing": ("Jarayonda", "y")}


def _search_filter(model, q: str):
    q = q.strip()
    m = re.fullmatch(r"(?i)vx-?[dt]?(\d+)", q)
    if m:
        return model.id == int(m.group(1))
    if q.isdigit():
        conds = [model.user_id == int(q), model.id == int(q)]
        if model is DonateOrder:
            conds.append(DonateOrder.player_id == q)
        return or_(*conds)
    name = q.lstrip("@").lower()
    if model is TgOrder:
        return or_(func.lower(TgOrder.target_username) == name, TgOrder.user_id.in_(select(User.id).where(func.lower(User.username) == name)))
    return model.user_id.in_(select(User.id).where(func.lower(User.username) == name))


@router.get("/orders")
async def orders(admin: AdminUser, session: SessionDep, kind: str = "all", state: str = "attention", q: str = "", limit: int = 60):
    limit = max(1, min(limit, 200))
    late = datetime.now(timezone.utc) - ATTENTION_AFTER
    items: list[dict] = []

    def donate_where(st: str):
        return {"attention": or_(DonateOrder.status == "review", (DonateOrder.status == "processing") & (DonateOrder.created_at < late)),
                "processing": DonateOrder.status == "processing", "done": DonateOrder.status == "done",
                "refunded": DonateOrder.status == "refunded"}.get(st, DonateOrder.status == "review")

    def tg_where(st: str):
        return {"attention": (TgOrder.status == "processing") & (or_(TgOrder.kind.not_in(("premium", "stars")), TgOrder.created_at < late)),
                "processing": TgOrder.status == "processing", "done": TgOrder.status == "done",
                "refunded": TgOrder.status == "refunded"}.get(st, TgOrder.status == "processing")

    counts = {}
    for st in ("attention", "processing"):
        counts[st] = int(await session.scalar(select(func.count()).select_from(DonateOrder).where(donate_where(st))) or 0) + \
            int(await session.scalar(select(func.count()).select_from(TgOrder).where(tg_where(st))) or 0)
    if kind in ("all", "donate"):
        stmt = select(DonateOrder).where(donate_where(state))
        if q.strip():
            stmt = select(DonateOrder).where(_search_filter(DonateOrder, q))
        dn = list(await session.scalars(stmt.order_by(DonateOrder.id.desc()).limit(limit)))
        provs = {p.id: p.name for p in await session.scalars(select(DonateProvider))}
        for o in dn:
            label, color = DONATE_ST.get(o.status, (o.status, "m"))
            if o.status == "processing" and o.created_at < late:
                label, color = "Kechikmoqda", "r"
            acts = [["retry", "Qayta", "y"]] if o.status == "review" else []
            if o.status in ("review", "processing"):
                acts += [["done", "Qo'lda bajarildi", "ok"], ["refund", "Qaytarish", "no"]]
            items.append({"kind": "donate", "id": o.id, "ref": f"VX-D{o.id}", "title": o.title, "game": o.game, "price": o.price,
                          "sub": f"ID {o.player_id}" + (f" ({o.zone_id})" if o.zone_id else "") + f" · user {o.user_id}",
                          "status": o.status, "label": label, "color": color, "error": o.error,
                          "provider": provs.get(o.package.provider_id) if o.package else None,
                          "at": o.created_at.isoformat() if o.created_at else None, "actions": acts})
    if kind in ("all", "tg"):
        stmt = select(TgOrder).where(tg_where(state))
        if q.strip():
            stmt = select(TgOrder).where(_search_filter(TgOrder, q))
        for o in await session.scalars(stmt.order_by(TgOrder.id.desc()).limit(limit)):
            label, color = TG_ST.get(o.status, (o.status, "m"))
            auto = (o.details or {}).get("auto") or {}
            if o.status == "processing" and (auto.get("manual") or o.kind not in ("premium", "stars")):
                label, color = "Qo'lda", "r"
            items.append({"kind": "tg", "id": o.id, "ref": f"VX-T{o.id}", "title": f"{o.title} → @{o.target_username.lstrip('@')}",
                          "game": None, "price": o.price, "sub": f"user {o.user_id}" + (f" · {auto.get('why')}" if auto.get("why") else ""),
                          "status": o.status, "label": label, "color": color, "error": None, "provider": "API" if o.kind in ("premium", "stars") else None,
                          "at": o.created_at.isoformat() if o.created_at else None,
                          "actions": [["done", "Bajarildi", "ok"], ["refund", "Qaytarish", "no"]] if o.status == "processing" else []})
    items.sort(key=lambda x: x["at"] or "", reverse=True)
    return {"items": items[:limit], "counts": counts}


# ------------------------------------------------------------------ katalog
_TAG = re.compile(r"\s*\(([^)]*)\)\s*")
GOOD_TAGS = {"", "global", "auto"}


def _base(name: str) -> tuple[str, str]:
    """«Mobile Legends (Global)» → ("mobilelegends", "global")."""
    tags = " ".join(_TAG.findall(name or "")).strip().lower()
    return re.sub(r"[^a-z0-9]", "", _TAG.sub(" ", name or "").lower()), tags


def _key(p: DonatePackage) -> tuple:
    return ("n", p.diamonds, p.bonus) if p.diamonds else ("s", re.sub(r"[^a-z0-9]", "", p.name.lower()))


def compare(cur: list[DonatePackage], alt: list[DonatePackage]) -> dict | None:
    """Bir xil paketlar (miqdor+bonus yoki nom) tannarxi bo'yicha: median farq %. Mos juftlik bo'lmasa — None."""
    a = {}
    for p in alt:
        c = _dec(p.cost_usd)
        if c and c > 0:
            a.setdefault(_key(p), c)
    diffs, ref = [], None
    for p in cur:
        c, k = _dec(p.cost_usd), _key(p)
        if c and c > 0 and k in a:
            diffs.append(float(a[k] / c - 1))
            if ref is None or (p.diamonds and p.diamonds < (ref[0].diamonds or 10**9)):
                ref = (p, c, a[k])
    if not diffs:
        return None
    return {"pct": round(statistics.median(diffs) * 100), "pairs": len(diffs),
            "ref": {"name": ref[0].name, "cur": str(ref[1]), "alt": str(ref[2])} if ref else None}


async def _alternatives(session, games: list[DonateGame]) -> dict[str, list[dict]]:
    """Har o'yin uchun boshqa API'dagi variantlar: bog'langan (shu o'yinda paketi bor) va bog'lanmagan (nomi mos yashirin o'yin)."""
    if not games:
        return {}
    provs = {p.id: p.name for p in await session.scalars(select(DonateProvider))}
    slugs = [g.slug for g in games]
    pk = list(await session.scalars(select(DonatePackage).where(DonatePackage.game.in_(slugs), DonatePackage.is_active.is_(True),
                                                                DonatePackage.provider_id.is_not(None))))
    others = list((await session.execute(select(DonateGame.slug, DonateGame.name, DonateGame.provider_id)
                                         .where(DonateGame.is_active.is_(False), DonateGame.provider_id.is_not(None)))).all())
    by_base: dict[str, list] = {}
    for slug, name, pid in others:
        b, tag = _base(name)
        if tag in GOOD_TAGS:
            by_base.setdefault(b, []).append((slug, name, pid))
    cand_slugs = []
    for g in games:
        cand_slugs += [s for s, _, pid in by_base.get(_base(g.name)[0], []) if pid != g.provider_id and s != g.slug]
    cand_pk = list(await session.scalars(select(DonatePackage).where(DonatePackage.game.in_(cand_slugs or [""]), DonatePackage.is_active.is_(True))))
    out: dict[str, list[dict]] = {}
    for g in games:
        cur = [p for p in pk if p.game == g.slug and p.provider_id == g.provider_id]
        res = []
        for pid in {p.provider_id for p in pk if p.game == g.slug and p.provider_id != g.provider_id}:
            cmp = compare(cur, [p for p in pk if p.game == g.slug and p.provider_id == pid])
            res.append({"provider_id": pid, "provider": provs.get(pid, "?"), "linked": True, "slug": g.slug, **(cmp or {"pct": None})})
        for s, name, pid in by_base.get(_base(g.name)[0], []):
            if pid == g.provider_id or s == g.slug or any(r["provider_id"] == pid for r in res):
                continue
            cmp = compare(cur, [p for p in cand_pk if p.game == s])
            res.append({"provider_id": pid, "provider": provs.get(pid, "?"), "linked": False, "slug": s, "name": name, **(cmp or {"pct": None})})
        out[g.slug] = sorted(res, key=lambda r: (r["pct"] is None, r["pct"] or 0))
    return out


def _gdict(g: DonateGame, n: int, provs: dict[int, str], alts: list[dict] | None = None) -> dict:
    logo = f"/api/donate/game-image/{g.slug}?v={g.image_ver}" if g.image_ver else g.logo_url
    best = next((a for a in (alts or []) if a.get("pct") is not None and a["pct"] <= -5), None)
    warn = "Paket yo'q" if n == 0 else ("Faqat 1 paket" if n == 1 else None)
    return {"slug": g.slug, "name": g.name, "logo": logo, "is_active": g.is_active, "sort": g.sort, "featured_slot": g.featured_slot,
            "popular": g.popular, "provider_id": g.provider_id, "provider": provs.get(g.provider_id or 0), "packages": n,
            "warning": warn if g.is_active else None, "cheaper": best, "providers": len((g.brands or {}))}


@router.get("/catalog/games")
async def catalog_games(admin: AdminUser, session: SessionDep, state: str = "active", q: str = "", limit: int = 80):
    limit = max(1, min(limit, 300))
    provs = {p.id: p.name for p in await session.scalars(select(DonateProvider))}
    stmt = select(DonateGame)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(DonateGame.name.ilike(like), DonateGame.slug.ilike(like)))
    if state == "hidden":
        stmt = stmt.where(DonateGame.is_active.is_(False))
    elif state != "all":
        stmt = stmt.where(DonateGame.is_active.is_(True))
    games = list(await session.scalars(stmt.order_by(DonateGame.sort, DonateGame.name).limit(limit)))
    counts = dict((await session.execute(select(DonatePackage.game, func.count()).where(
        DonatePackage.is_active.is_(True), DonatePackage.game.in_([g.slug for g in games] or [""]),
        or_(DonatePackage.provider_id.is_(None), DonatePackage.provider_id == select(DonateGame.provider_id)
            .where(DonateGame.slug == DonatePackage.game).scalar_subquery())).group_by(DonatePackage.game))).all())
    active = [g for g in games if g.is_active]
    alts = await _alternatives(session, active) if state in ("active", "cheaper") else {}
    items = [_gdict(g, counts.get(g.slug, 0), provs, alts.get(g.slug)) for g in games]
    if state == "cheaper":
        items = [x for x in items if x["cheaper"]]
    n_active = int(await session.scalar(select(func.count()).select_from(DonateGame).where(DonateGame.is_active.is_(True))) or 0)
    n_hidden = int(await session.scalar(select(func.count()).select_from(DonateGame).where(DonateGame.is_active.is_(False))) or 0)
    return {"items": items, "counts": {"active": n_active, "hidden": n_hidden,
                                       "cheaper": sum(1 for g in active if any((a.get("pct") or 0) <= -5 for a in alts.get(g.slug, [])))},
            "rate": int(await app_settings.get_value(session, "donate_usd_rate")),
            "markup": int(await app_settings.get_value(session, "donate_markup_percent"))}


class OrderIn(BaseModel):
    slugs: list[str] = Field(max_length=200)


@router.put("/catalog/order")
async def catalog_order(body: OrderIn, admin: AdminUser, session: SessionDep):
    """Bosh sahifadagi tartib: ro'yxat tartibida 0, 10, 20 ..."""
    async with session.begin():
        for i, s in enumerate(body.slugs):
            await session.execute(update(DonateGame).where(DonateGame.slug == s).values(sort=i * 10))
    await invalidate_packages_cache()
    return {"ok": True}


def _group(p: DonatePackage) -> str:
    n = p.name.lower()
    if any(w in n for w in ("pass", "weekly", "monthly", "membership", "card", "prime", "welkin", "elite")):
        return "pass"
    return "amount" if p.diamonds else "other"


@router.get("/catalog/games/{slug}")
async def catalog_game(slug: str, admin: AdminUser, session: SessionDep, provider_id: int | None = None):
    g = await session.get(DonateGame, slug)
    if g is None:
        raise NotFound("O'yin")
    rate = int(await app_settings.get_value(session, "donate_usd_rate"))
    provs = {p.id: p.name for p in await session.scalars(select(DonateProvider))}
    alts = (await _alternatives(session, [g])).get(g.slug, [])
    view = provider_id or g.provider_id
    stmt = select(DonatePackage).where(DonatePackage.game == slug)
    if view:
        stmt = stmt.where(or_(DonatePackage.provider_id == view, DonatePackage.provider_id.is_(None)))
    pk = list(await session.scalars(stmt.order_by(DonatePackage.sort, DonatePackage.price)))
    packages = []
    for p in pk:
        c = _dec(p.cost_usd)
        packages.append({"id": p.id, "name": p.name, "diamonds": p.diamonds, "bonus": p.bonus, "price": p.price, "cost_usd": p.cost_usd,
                         "profit": int(p.price - c * rate) if c is not None else None, "is_active": p.is_active, "is_hot": p.is_hot,
                         "source": p.source, "delivery": p.delivery, "group": _group(p), "provider_id": p.provider_id})
    n = sum(1 for p in pk if p.is_active)
    return {"game": _gdict(g, n, provs, alts), "fields": g.fields or [], "view_provider_id": view,
            "providers": ([{"provider_id": g.provider_id, "provider": provs.get(g.provider_id), "current": True, "linked": True, "pct": 0}]
                          if g.provider_id else []) + alts,
            "packages": packages, "rate": rate}


class ProvIn(BaseModel):
    provider_id: int


@router.post("/catalog/games/{slug}/provider")
async def catalog_switch(slug: str, body: ProvIn, admin: AdminUser, session: SessionDep):
    """O'yin qaysi API orqali sotiladi. Faqat shu o'yinga bog'langan (paketi bor) API tanlanadi."""
    async with session.begin():
        g = await session.get(DonateGame, slug, with_for_update=True)
        if g is None:
            raise NotFound("O'yin")
        brand = (g.brands or {}).get(str(body.provider_id))
        if not brand:
            raise BadState("Bu API shu o'yinga bog'lanmagan — avval «Bog'lash» ni bosing")
        g.provider_id, g.brand_slug = body.provider_id, brand
    await invalidate_packages_cache()
    return {"ok": True}


class LinkIn(BaseModel):
    from_slug: str = Field(max_length=64)


@router.post("/catalog/games/{slug}/link")
async def catalog_link(slug: str, body: LinkIn, admin: AdminUser, session: SessionDep):
    """Boshqa API'dagi o'yinni shu o'yinga qo'shish (masalan FazerCards «Mobile Legends (Global)» → ML).
    Paketlari shu o'yinga o'tadi, keyingi sinxronlashlar ham shu yerga yozadi. Sotuv API'si o'zgarmaydi — alohida tanlanadi."""
    async with session.begin():
        g = await session.get(DonateGame, slug, with_for_update=True)
        src = await session.get(DonateGame, body.from_slug, with_for_update=True)
        if g is None or src is None or src.slug == g.slug:
            raise NotFound("O'yin")
        pid = src.provider_id
        if not pid:
            raise BadState("Bu o'yin hech qaysi API'ga tegishli emas")
        if pid == g.provider_id:
            raise BadState("Bu o'yin shu API'ning o'zida — boshqa API'dagisini tanlang")
        prov = await session.get(DonateProvider, pid, with_for_update=True)
        brand = (src.brands or {}).get(str(pid)) or src.brand_slug or src.slug
        old = (g.brands or {}).get(str(pid))
        mp = dict((prov.config or {}).get("map") or {})
        if old and old != brand:  # shu API'dan avval boshqa variant bog'langan edi — uni ajratamiz
            mp.pop(old, None)
            await session.execute(update(DonatePackage).where(DonatePackage.game == g.slug, DonatePackage.provider_id == pid).values(is_active=False))
        mp[brand] = g.slug
        prov.config = {**(prov.config or {}), "map": mp}
        await session.execute(update(DonatePackage).where(DonatePackage.game == src.slug, DonatePackage.provider_id == pid).values(game=g.slug))
        g.brands = {**(g.brands or {}), str(pid): brand}
        if g.provider_id is None:
            g.provider_id, g.brand_slug = pid, brand
        await session.delete(src)
    donate_catalog.forget_provider(pid)
    await invalidate_packages_cache()
    return {"ok": True}


class PkgPatch(BaseModel):
    is_active: bool | None = None
    is_hot: bool | None = None


@router.patch("/catalog/packages/{pkg_id}")
async def catalog_package(pkg_id: int, body: PkgPatch, admin: AdminUser, session: SessionDep):
    async with session.begin():
        p = await session.get(DonatePackage, pkg_id)
        if p is None:
            raise NotFound("Paket")
        if body.is_active is not None:
            p.is_active = body.is_active
            if p.source == "api":
                p.admin_off = not body.is_active  # sinxronlash qayta yoqmasin
        if body.is_hot is not None:
            p.is_hot = body.is_hot
    await invalidate_packages_cache()
    return {"ok": True, "is_active": p.is_active, "is_hot": p.is_hot}


@router.get("/catalog/games/{slug}/candidates")
async def catalog_candidates(slug: str, admin: AdminUser, session: SessionDep, q: str = ""):
    """Bog'lash uchun: boshqa API'lardagi yashirin o'yinlar (nom bo'yicha)."""
    g = await session.get(DonateGame, slug)
    if g is None:
        raise NotFound("O'yin")
    provs = {p.id: p.name for p in await session.scalars(select(DonateProvider))}
    like = f"%{(q or _TAG.sub(' ', g.name)).strip()}%"
    rows = await session.scalars(select(DonateGame).where(DonateGame.is_active.is_(False), DonateGame.provider_id.is_not(None),
                                                          DonateGame.provider_id != (g.provider_id or 0), DonateGame.name.ilike(like))
                                 .order_by(DonateGame.name).limit(40))
    return [{"slug": x.slug, "name": x.name, "provider_id": x.provider_id, "provider": provs.get(x.provider_id)} for x in rows]


# ------------------------------------------------------------------ bot holati (ochiq/yopiq, mehmonlar)
class OpenIn(BaseModel):
    open: bool


@router.post("/bot/open")
async def bot_open(body: OpenIn, admin: AdminUser):
    await launch.set_open(body.open)
    return {"open": body.open}


@router.get("/bot/guests")
async def bot_guests(admin: AdminUser, session: SessionDep):
    ids = sorted(await launch.guests())
    users = await _users(session, ids)
    return [{"id": i, "name": _uname(users.get(i)), "known": i in users} for i in ids]


class GuestIn(BaseModel):
    id: int = Field(gt=0, lt=10**13)
    add: bool = True


@router.post("/bot/guests")
async def bot_guest(body: GuestIn, admin: AdminUser):
    ids = await launch.guests()
    (ids.add if body.add else ids.discard)(body.id)
    await launch.set_guests(ids)
    return {"ok": True, "count": len(ids)}
