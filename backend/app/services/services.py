"""TG xizmatlar, Boost, Arena va pul yechish."""

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError, BadState, Forbidden, NotFound
from app.models import BoostOrder, TgOrder, Tournament, TournamentEntry, User, Withdrawal
from app.security import encrypt
from app.services import catalog, wallet
from app.services.notify import Outbox, fmt, webapp_button

USERNAME_RE = re.compile(r"^@?[A-Za-z][A-Za-z0-9_]{3,31}$")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def clean_username(value: str) -> str:
    value = (value or "").strip()
    if not USERNAME_RE.match(value):
        raise AppError("bad_username", "Telegram username noto'g'ri (masalan: @username)")
    return "@" + value.lstrip("@")


# ================================================================ TG xizmatlar
async def create_tg_order(session: AsyncSession, user: User, data: dict, out: Outbox) -> TgOrder:
    kind = data.get("kind")
    target = data.get("target_username") or ""
    if data.get("for_self"):
        if not user.username:
            raise AppError("no_username", "Telegram profilingizda username yo'q — username'ni qo'lda kiriting")
        target = user.username
    target = clean_username(target)
    details: dict = {}
    prices = await catalog.tg_prices(session)
    if kind == "premium":
        months = int(data.get("months") or 0)
        if months not in prices["premium"]:
            raise AppError("bad_months", "Muddatni tanlang")
        price, title = prices["premium"][months], f"Telegram Premium · {months} oy"
        details["months"] = months
    elif kind == "stars":
        amount = int(data.get("stars") or 0)
        if not catalog.STARS_MIN <= amount <= catalog.STARS_MAX:
            raise AppError("bad_stars", f"Stars soni {catalog.STARS_MIN} dan kam bo'lmasin")
        bonus = prices.get("stars_bonus", {}).get(amount, 0)
        price = catalog.stars_total(amount, prices["star_x100"])
        title = f"Telegram Stars · {amount:,}".replace(",", " ") + (f" + {bonus} bonus" if bonus else "")
        details["stars"] = amount
        if bonus:
            details["bonus"] = bonus
    elif kind == "gift":
        code = data.get("gift")
        if code not in prices["gifts"]:
            raise AppError("bad_gift", "Sovg'ani tanlang")
        name, price = prices["gifts"][code]
        title = f"Telegram Gift · {name}"
        details.update(gift=code, message=(data.get("message") or "")[:200], anonymous=bool(data.get("anonymous")))
    elif kind == "nft":
        code = data.get("nft")
        if code not in prices["nft"]:
            raise AppError("bad_nft", "NFT turini tanlang")
        name, price = prices["nft"][code]
        title = f"Telegram NFT · {name}"
        details.update(nft=code, link=(data.get("link") or "")[:200])
    else:
        raise AppError("bad_kind", "Xizmat turini tanlang")
    details["note"] = (data.get("note") or "")[:300]
    details["price_mode"] = prices["mode"]
    order = TgOrder(user_id=user.id, kind=kind, title=title, target_username=target, details=details, price=price)
    session.add(order)
    await session.flush()
    await wallet.debit(session, user.id, price, "tg_service", f"tg:{order.id}", ref_type="tg", ref_id=order.id)
    out.admins(f"⭐️ Yangi TG buyurtma #{order.id}\n{title}\nKimga: {target}\nSumma: {fmt(price)}", webapp_button("Bajarish", "/admin"), topic="buyurtma")
    return order


async def resolve_tg_order(session: AsyncSession, order_id: int, action: str, note: str, out: Outbox) -> TgOrder:
    order = await session.scalar(select(TgOrder).where(TgOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if order is None:
        raise NotFound("Buyurtma")
    if order.status != "processing":
        raise BadState("Buyurtma yakunlangan")
    order.admin_note = (note or "")[:300] or None
    order.finished_at = _now()
    if action == "done":
        order.status = "done"
        await wallet.add_ticket(session, order.user_id)
        out.user(order.user_id, f"✅ {order.title} bajarildi ({order.target_username}).")
    elif action == "refund":
        order.status = "refunded"
        await wallet.credit(session, order.user_id, order.price, "tg_refund", f"tg:{order.id}:refund", ref_type="tg", ref_id=order.id)
        out.user(order.user_id, f"↩️ {order.title} bajarilmadi, {fmt(order.price)} qaytarildi." + (f"\nSabab: {note}" if note else ""))
    else:
        raise AppError("bad_action", "Noma'lum amal")
    return order


# ================================================================ Boost
def boost_quote(data: dict, pct: dict) -> dict:
    """Narx: yulduzlar bo'yicha asosiy narx + tanlangan qo'shimchalar ustamasi (foizlar admin paneldan)."""
    cur = data.get("current_rank")
    if cur not in ("Epic", "Legend", "Mythic"):
        raise AppError("bad_rank", "Hozirgi rankni tanlang")
    div = data.get("current_division") or "V"
    if div not in catalog.DIVISIONS:
        raise AppError("bad_rank", "Darajani tanlang")
    target = data.get("target_rank")
    if target not in catalog.TARGETS:
        raise AppError("bad_rank", "Maqsad rankni tanlang")
    try:
        base, start, end = catalog.boost_price(
            cur, div, int(data.get("current_stars") or 0), target, int(data.get("target_stars") or 0),
            catalog.star_table(pct) if "boost_star_epic" in pct else None,
        )
    except ValueError as e:
        raise AppError("bad_rank", str(e)) from e
    extras = []
    if data.get("express"):
        extras.append(("express", "Express", pct["boost_express_percent"]))
    if data.get("hero"):
        extras.append(("hero", f"Qahramon: {str(data['hero'])[:32]}", pct["boost_hero_percent"]))
    if data.get("lane"):
        if data["lane"] not in catalog.LANES[1:]:
            raise AppError("bad_lane", "Liniya noto'g'ri")
        extras.append(("lane", f"Liniya: {data['lane']}", pct["boost_lane_percent"]))
    lines = [{"key": k, "label": lbl, "percent": p, "amount": base * p // 100} for k, lbl, p in extras]
    stars = end - start
    per_day = int(pct.get("boost_express_stars_per_day" if data.get("express") else "boost_stars_per_day") or 15)
    days = max(1, -(-stars // per_day))
    return {"base": base, "extras": lines, "price": base + sum(x["amount"] for x in lines), "stars": stars,
            "days": f"{days}–{days + 1}", "percents": pct}


def _rank_label(rank: str, division: str, stars: int) -> str:
    return f"Mythic {stars}★" if rank == "Mythic" else f"{rank} {division}"


async def boost_percents(session: AsyncSession) -> dict:
    from app.services import app_settings

    return await app_settings.get_many(
        session, "boost_express_percent", "boost_hero_percent", "boost_lane_percent",
        "boost_star_epic", "boost_star_legend", "boost_star_mythic", "boost_star_honor", "boost_star_glory",
        "boost_stars_per_day", "boost_express_stars_per_day",
    )


async def create_boost(session: AsyncSession, user: User, data: dict, out: Outbox) -> BoostOrder:
    q = boost_quote(data, await boost_percents(session))
    method = data.get("login_method")
    if method not in catalog.LOGIN_METHODS:
        raise AppError("bad_login", "Kirish usulini tanlang")
    creds = (data.get("credentials") or "").strip()
    if method in ("moonton", "google") and len(creds) < 3:
        raise AppError("bad_credentials", "Kirish ma'lumotlarini kiriting")
    target = data["target_rank"]
    target_stars = int(data.get("target_stars") or 0)
    extras = ", ".join(x["label"] for x in q["extras"])
    note = (data.get("note") or "")[:400]
    order = BoostOrder(
        user_id=user.id,
        game=data.get("game") if data.get("game") in ("ML", "MC") else "ML",
        current_rank=_rank_label(data["current_rank"], data.get("current_division") or "V", int(data.get("current_stars") or 0)),
        target_rank="Legend I" if target == "Legend" else f"{target} {target_stars}★",
        stars=q["stars"],
        lane=(data.get("lane") or "")[:16],
        note=(f"[{extras}] " if extras else "") + note,
        login_method=method,
        credentials_enc=encrypt(creds) if creds else None,
        price=q["price"],
    )
    u = await session.get(User, user.id, with_for_update=True)
    if u.boost_coupon_percent > 0:  # ball evaziga olingan chegirma — bir martalik
        off = order.price * u.boost_coupon_percent // 100
        order.price -= off
        order.note = f"[Ball chegirmasi −{u.boost_coupon_percent}%] " + order.note
        u.boost_coupon_percent = 0
    session.add(order)
    await session.flush()
    await wallet.debit(session, user.id, order.price, "boost", f"boost:{order.id}", ref_type="boost", ref_id=order.id)
    return order




async def boost_accept(session: AsyncSession, order_id: int, booster: User, out: Outbox) -> BoostOrder:
    order = await session.scalar(select(BoostOrder).where(BoostOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if order is None:
        raise NotFound("Buyurtma")
    if order.status != "searching":
        raise BadState("Buyurtmani boshqa booster oldi")
    if order.user_id == booster.id:
        raise Forbidden("O'z buyurtmangizni ololmaysiz")
    order.status = "accepted"
    order.accepted_at = _now()
    order.booster_id = booster.id
    order.booster_name = booster.username or booster.first_name
    out.user(order.user_id, f"🤝 Booster buyurtma #{order.id} ni qabul qildi. Ishni boshlaganda xabar beramiz.")
    return order


async def boost_progress(session: AsyncSession, order_id: int, booster_id: int, step: str, out: Outbox) -> BoostOrder:
    order = await session.scalar(select(BoostOrder).where(BoostOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if order is None or order.booster_id != booster_id:
        raise NotFound("Buyurtma")
    if step == "start" and order.status == "accepted":
        order.status = "in_progress"
        order.started_at = _now()
        out.user(order.user_id, f"🚀 Booster ishni boshladi: {order.current_rank} → {order.target_rank}")
    elif step == "finish" and order.status == "in_progress":
        order.status = "finished"
        order.finished_at = _now()  # avto-tasdiq shu vaqtdan hisoblanadi
        out.user(
            order.user_id,
            f"🏁 Booster ishni tugatdi: {order.target_rank}. Akkauntni tekshirib, tasdiqlang. "
            f"{settings.escrow_auto_release_hours} soatda avtomatik tasdiqlanadi.",
            webapp_button("Tasdiqlash", f"/boost/{order.id}"),
        )
    else:
        raise BadState()
    return order


async def boost_complete(session: AsyncSession, order: BoostOrder, out: Outbox) -> None:
    order.status = "done"
    order.finished_at = _now()
    order.credentials_enc = None  # parol endi kerak emas — o'chiriladi
    from app.services import app_settings

    share = order.price * int(await app_settings.get_value(session, "booster_share_percent")) // 100
    if order.booster_id and share > 0:
        await wallet.credit(session, order.booster_id, share, "boost_payout", f"boost:{order.id}:payout", ref_type="boost", ref_id=order.id)
        out.user(order.booster_id, f"💸 Buyurtma #{order.id} tasdiqlandi: +{fmt(share)}")
    out.user(order.user_id, f"✅ Boost #{order.id} yakunlandi. Rahmat!")


async def boost_client_action(session: AsyncSession, order_id: int, user_id: int, action: str, reason: str, out: Outbox) -> BoostOrder:
    order = await session.scalar(select(BoostOrder).where(BoostOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if order is None or order.user_id != user_id:
        raise NotFound("Buyurtma")
    if action == "confirm" and order.status == "finished":
        await boost_complete(session, order, out)
    elif action == "cancel" and order.status == "searching":
        order.status = "refunded"
        order.finished_at = _now()
        order.credentials_enc = None
        await wallet.credit(session, user_id, order.price, "boost_refund", f"boost:{order.id}:refund", ref_type="boost", ref_id=order.id)
    elif action == "dispute" and order.status in ("accepted", "in_progress", "finished"):
        order.status = "disputed"
        order.note = (order.note + f"\n[Nizo] {reason}")[:500]
        out.admins(f"⚖️ Boost nizosi #{order.id}: {reason[:300]}", webapp_button("Admin panel", "/admin"), topic="nizo")
    else:
        raise BadState()
    return order


async def boost_admin_resolve(session: AsyncSession, order_id: int, action: str, out: Outbox) -> BoostOrder:
    order = await session.scalar(select(BoostOrder).where(BoostOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if order is None:
        raise NotFound("Buyurtma")
    if order.status in ("done", "refunded"):
        raise BadState("Buyurtma yakunlangan")
    if action == "done":
        await boost_complete(session, order, out)
    elif action == "refund":
        order.status = "refunded"
        order.finished_at = _now()
        order.credentials_enc = None
        await wallet.credit(session, order.user_id, order.price, "boost_refund", f"boost:{order.id}:refund", ref_type="boost", ref_id=order.id)
        out.user(order.user_id, f"↩️ Boost #{order.id} bekor qilindi, {fmt(order.price)} qaytarildi.")
    else:
        raise AppError("bad_action", "Noma'lum amal")
    return order


async def boost_auto_confirm(session: AsyncSession, out: Outbox) -> int:
    from datetime import timedelta

    limit_time = _now() - timedelta(hours=settings.escrow_auto_release_hours)
    ids = list(await session.scalars(
        select(BoostOrder.id).where(BoostOrder.status == "finished", BoostOrder.finished_at <= limit_time).limit(100)
    ))
    for oid in ids:
        order = await session.scalar(select(BoostOrder).where(BoostOrder.id == oid).with_for_update().execution_options(populate_existing=True))
        if order.status == "finished":
            await boost_complete(session, order, out)
    return len(ids)


# ================================================================ Arena
async def join_tournament(session: AsyncSession, t_id: int, user_id: int, data: dict) -> TournamentEntry:
    t = await session.scalar(select(Tournament).where(Tournament.id == t_id).with_for_update().execution_options(populate_existing=True))
    if t is None:
        raise NotFound("Turnir")
    if t.status != "open" or t.starts_at <= _now():
        raise BadState("Ro'yxatdan o'tish yopilgan")
    if t.players_count >= t.max_players:
        raise BadState("Joylar tugagan")
    if await session.scalar(select(TournamentEntry.id).where(TournamentEntry.tournament_id == t_id, TournamentEntry.user_id == user_id)):
        raise BadState("Siz allaqachon ro'yxatdasiz")
    nick = (data.get("nick") or "").strip()[:64]
    game_id = (data.get("game_id") or "").strip()[:32]
    if not nick or not game_id:
        raise AppError("bad_entry", "Nik va o'yin ID'sini kiriting")
    entry = TournamentEntry(
        tournament_id=t_id, user_id=user_id, nick=nick, game_id=game_id,
        server=(data.get("server") or "").strip()[:16], tg_username=(data.get("tg_username") or "").strip()[:64],
    )
    session.add(entry)
    await session.flush()
    if t.entry_fee > 0:
        user = await session.get(User, user_id, with_for_update=True)
        if data.get("use_pass") and user.tournament_passes > 0:
            user.tournament_passes -= 1  # ball evaziga olingan bepul kirish
        else:
            await wallet.debit(session, user_id, t.entry_fee, "tournament_fee", f"tour:{t_id}:{user_id}", ref_type="tournament", ref_id=t_id)
    t.players_count += 1
    from app.services import app_settings, arena

    pts = int(await app_settings.get_value(session, "pts_tournament_join"))
    await arena.add_points(session, user_id, pts, "tournament_join", f"tour_join:{t_id}:{user_id}")
    await arena.bump(session, user_id, "join_tournament")
    await arena.bump(session, user_id, "play_3")
    return entry


# ================================================================ Pul yechish
CARD_RE = re.compile(r"^\d{16}$")


async def create_withdrawal(session: AsyncSession, user_id: int, amount: int, card: str, holder: str, out: Outbox) -> Withdrawal:
    card = re.sub(r"\D", "", card or "")
    if not CARD_RE.match(card):
        raise AppError("bad_card", "Karta raqami 16 ta raqam bo'lishi kerak")
    if amount < settings.withdraw_min:
        raise AppError("bad_amount", f"Eng kam yechish summasi {fmt(settings.withdraw_min)}")
    pending = await session.scalar(select(Withdrawal.id).where(Withdrawal.user_id == user_id, Withdrawal.status == "pending"))
    if pending:
        raise BadState("Oldingi so'rovingiz hali ko'rib chiqilmoqda")
    user = await session.get(User, user_id, with_for_update=True)  # parallel so'rovlarga qarshi
    w_info = await wallet.withdrawable(session, user_id, user.balance)
    if w_info["earned"] <= 0:
        raise AppError("no_earnings", "Pul yechish faqat sotuvchi, ijaraga beruvchi va boosterlar uchun — ishlab topilgan pul yechiladi", 403)
    if amount > w_info["available"]:
        raise AppError("over_limit", f"Yechish mumkin: {fmt(w_info['available'])} (faqat sotuv, ijara va boost daromadi)")
    w = Withdrawal(user_id=user_id, amount=amount, card_number=card, card_holder=(holder or "").strip()[:64])
    session.add(w)
    await session.flush()
    await wallet.debit(session, user_id, amount, "withdraw", f"withdraw:{w.id}", ref_type="withdraw", ref_id=w.id)
    out.admins(f"💳 Pul yechish so'rovi #{w.id}: {fmt(amount)}\nKarta: {card} {w.card_holder}", webapp_button("Admin panel", "/admin"), topic="yechish")
    return w


async def resolve_withdrawal(session: AsyncSession, w_id: int, action: str, note: str, out: Outbox) -> Withdrawal:
    w = await session.scalar(select(Withdrawal).where(Withdrawal.id == w_id).with_for_update().execution_options(populate_existing=True))
    if w is None:
        raise NotFound("So'rov")
    if w.status != "pending":
        raise BadState("So'rov ko'rib chiqilgan")
    w.processed_at = _now()
    w.admin_note = (note or "")[:300] or None
    if action == "paid":
        w.status = "paid"
        out.user(w.user_id, f"✅ {fmt(w.amount)} kartangizga o'tkazildi (*{w.card_number[-4:]}).")
    elif action == "reject":
        w.status = "rejected"
        await wallet.credit(session, w.user_id, w.amount, "withdraw_refund", f"withdraw:{w.id}:refund", ref_type="withdraw", ref_id=w.id)
        out.user(w.user_id, f"↩️ Pul yechish rad etildi, {fmt(w.amount)} hamyonga qaytarildi." + (f"\nSabab: {note}" if note else ""))
    else:
        raise AppError("bad_action", "Noma'lum amal")
    return w


async def tournament_reminders(session: AsyncSession, out: Outbox) -> int:
    """Boshlanishiga 30 daqiqa qolgan turnir ishtirokchilariga eslatma (o'chirib qo'yish mumkin)."""
    from datetime import datetime, timedelta, timezone

    from app.services.notify import webapp_button

    now = datetime.now(timezone.utc)
    tours = list(await session.scalars(
        select(Tournament).where(
            Tournament.reminded.is_(False), Tournament.status.in_(("open", "running")),
            Tournament.starts_at <= now + timedelta(minutes=30), Tournament.starts_at > now - timedelta(minutes=5),
        ).with_for_update(skip_locked=True)
    ))
    for t in tours:
        t.reminded = True
        uids = await session.scalars(select(TournamentEntry.user_id).where(TournamentEntry.tournament_id == t.id))
        for uid in uids:
            out.user(uid, f"⏰ «{t.title}» turniri 30 daqiqadan keyin boshlanadi. Tayyor turing!",
                     webapp_button("Turnirni ochish", f"/arena/{t.id}"), kind="tour")
    return len(tours)


async def boost_report_progress(session: AsyncSession, order_id: int, booster_id: int, stars_done: int,
                                winrate: int | None, out: Outbox) -> BoostOrder:
    """Booster progressni yuboradi (/progress). Mijozga bot orqali xabar boradi."""
    order = await session.scalar(select(BoostOrder).where(BoostOrder.id == order_id).with_for_update().execution_options(populate_existing=True))
    if order is None or order.booster_id != booster_id:
        raise NotFound("Buyurtma")
    if order.status not in ("accepted", "in_progress"):
        raise BadState("Buyurtma faol emas")
    if order.status == "accepted":
        order.status, order.started_at = "in_progress", _now()
    order.progress_stars = max(0, min(order.stars, stars_done))
    if winrate is not None:
        order.winrate = max(0, min(100, winrate))
    left = order.stars - order.progress_stars
    out.user(order.user_id, f"📈 Boost #{order.id}: {order.progress_stars}/{order.stars} yulduz olindi, {left} ta qoldi."
             + (f" Win-rate: {order.winrate}%" if order.winrate is not None else ""),
             webapp_button("Jonli progress", f"/boost/{order.id}"))
    return order
