"""Draft Jang: ikki o'yinchi bir xil qoidada 5 ta qahramon tanlaydi (har liniyaga bittadan), tizim draftlarni baholab g'olibni aytadi.

Ball (hamma uchun ochiq formula):
  * liniyaga mos qahramon: har biri +8 (eng ko'pi 40)
  * oldingi qator (tank/support) bor: +12 · strelok bor: +12 · mag bor: +12
  * jismoniy va sehrli zarar aralash: +10
  * bir xil roldan 3 tadan ko'p bo'lmasa: +6
  * raqibning har bir qahramoniga counter bo'lgan har qahramon uchun +5 (jonli statistika bo'lsa; eng ko'pi 25)
Draft ELO: 1000 dan boshlanadi, g'alaba/durang/mag'lubiyatga qarab o'zgaradi (K=24).
Tanlovlar ikkalasi ham topshirguncha yashirin (ko'r draft).
"""

import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError, BadState, Forbidden, NotFound
from app.models import DraftDuel, User
from app.services import app_settings, arena, mlbb
from app.services.notify import Outbox, webapp_button

SLOTS = ("gold", "exp", "mid", "jungle", "roam")
SLOT_LABEL = {"gold": "Gold", "exp": "EXP", "mid": "Mid", "jungle": "Jungle", "roam": "Roam"}
FRONT = {"tank", "support"}
PHYSICAL = {"marksman", "fighter", "assassin"}
DUEL_HOURS = 48
ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def link(bot_username: str, code: str) -> str | None:
    return f"https://t.me/{bot_username}?start=duel_{code}" if bot_username else None


def clean_picks(data: dict) -> dict[str, int]:
    heroes = mlbb.heroes()
    out: dict[str, int] = {}
    for slot in SLOTS:
        try:
            hid = int((data or {}).get(slot))
        except (TypeError, ValueError):
            raise AppError("bad_picks", "Har liniyaga bittadan qahramon tanlang") from None
        if hid not in heroes:
            raise AppError("bad_picks", "Noma'lum qahramon")
        out[slot] = hid
    if len(set(out.values())) != 5:
        raise AppError("bad_picks", "Bitta qahramonni ikki marta tanlab bo'lmaydi")
    return out


def score_draft(picks: dict[str, int], enemy: dict[str, int], counters: dict[int, set[int]] | None = None) -> dict:
    """Draftni baholaydi. counters: {raqib qahramoni: unga counter bo'lgan qahramonlar}."""
    heroes = mlbb.heroes()
    mine = {s: heroes[h] for s, h in picks.items()}
    roles = [h["role"] for h in mine.values()]
    lane_fit = sum(8 for s, h in mine.items() if h["lane"] == s)
    front = 12 if any(r in FRONT for r in roles) else 0
    marks = 12 if "marksman" in roles else 0
    mage = 12 if "mage" in roles else 0
    mixed = 10 if ("mage" in roles and any(r in PHYSICAL for r in roles)) else 0
    spread = 6 if max(roles.count(r) for r in set(roles)) <= 2 else 0
    cnt = 0
    if counters:
        mine_ids = set(picks.values())
        cnt = min(25, 5 * sum(1 for e in enemy.values() if counters.get(e, set()) & mine_ids))
    parts = {"lane": lane_fit, "front": front, "marksman": marks, "mage": mage, "mixed": mixed, "spread": spread, "counter": cnt}
    return {"total": sum(parts.values()), "parts": parts}


async def _live_counters(enemy_ids) -> dict[int, set[int]]:
    """Jonli statistikadan counter'lar (Rone Arena). Ishlamasa — bo'sh (ball faqat tarkib bo'yicha)."""
    from app.services import mlstats

    out: dict[int, set[int]] = {}
    for hid in set(enemy_ids):
        try:
            data = await mlstats.counters(hid)
            out[hid] = {int(c["hero"]) if isinstance(c, dict) and "hero" in c else int(c) for c in data.get("counters", [])}
        except Exception:  # noqa: BLE001 — tashqi API: ishlamasa o'tkazib yuboramiz
            continue
    return out


def expected(ra: int, rb: int) -> float:
    return 1 / (1 + 10 ** ((rb - ra) / 400))


def elo_delta(ra: int, rb: int, score_a: float, k: int = 24) -> int:
    return round(k * (score_a - expected(ra, rb)))


async def enabled(session: AsyncSession) -> bool:
    return await app_settings.get_value(session, "duel_on") == "on"


async def create(session: AsyncSession, user_id: int) -> DraftDuel:
    if not await enabled(session):
        raise BadState("Draft Jang hozircha yopiq")
    n = await session.scalar(select(func.count()).select_from(DraftDuel).where(
        DraftDuel.a_id == user_id, DraftDuel.status.in_(("waiting", "picking")), DraftDuel.expires_at > _now()))
    if (n or 0) >= 3:
        raise BadState("Bir vaqtda 3 tadan ko'p ochiq jang bo'lishi mumkin emas")
    d = DraftDuel(code="".join(secrets.choice(ALPHABET) for _ in range(8)), a_id=user_id, status="waiting", a_score=0, b_score=0,
                  a_delta=0, b_delta=0, expires_at=_now() + timedelta(hours=DUEL_HOURS))
    session.add(d)
    await session.flush()
    return d


async def _lock(session: AsyncSession, code: str) -> DraftDuel:
    d = await session.scalar(select(DraftDuel).where(DraftDuel.code == code).with_for_update().execution_options(populate_existing=True))
    if d is None:
        raise NotFound("Jang")
    return d


async def join(session: AsyncSession, user_id: int, code: str, out: Outbox) -> DraftDuel:
    d = await _lock(session, code)
    if d.a_id == user_id or d.b_id == user_id:
        return d
    if d.b_id is not None or d.status != "waiting" or d.expires_at <= _now():
        raise BadState("Bu jangga qo'shilib bo'lmaydi")
    d.b_id, d.status = user_id, "picking"
    joiner = await session.get(User, user_id)
    out.user(d.a_id, f"⚔️ {(joiner.first_name or 'Raqib')[:24]} Draft Jangga qo'shildi! Endi draftingizni tanlang.", webapp_button("Jang", f"/duel/{d.code}"))
    return d


async def submit(session: AsyncSession, user_id: int, code: str, picks: dict, out: Outbox) -> tuple[DraftDuel, bool]:
    """Draftni topshiradi. Ikkalasi topshirgach natija hisoblanadi (True qaytadi — ELO va xabarlar tayyor)."""
    d = await _lock(session, code)
    if user_id not in (d.a_id, d.b_id):
        raise Forbidden()
    if d.status not in ("picking",) or d.expires_at <= _now():
        raise BadState("Hozir draft topshirib bo'lmaydi")
    clean = clean_picks(picks)
    if user_id == d.a_id:
        if d.a_picks:
            raise BadState("Draftingiz allaqachon topshirilgan")
        d.a_picks = clean
    else:
        if d.b_picks:
            raise BadState("Draftingiz allaqachon topshirilgan")
        d.b_picks = clean
    if not (d.a_picks and d.b_picks):
        other = d.b_id if user_id == d.a_id else d.a_id
        out.user(other, "⏳ Raqib draftini topshirdi. Navbat sizda!", webapp_button("Jang", f"/duel/{d.code}"))
        return d, False
    return d, True


async def resolve(session: AsyncSession, code: str, out: Outbox) -> DraftDuel:
    """Ikkala draft ham tayyor: ball, g'olib, ELO. (Jonli counter so'rovlari tarmoqqa chiqadi — tranzaksiyadan tashqarida chaqiring.)"""
    d = await _lock(session, code)
    if d.status != "picking" or not (d.a_picks and d.b_picks):
        return d
    counters = await _live_counters([*d.a_picks.values(), *d.b_picks.values()])
    sa = score_draft(d.a_picks, d.b_picks, counters)
    sb = score_draft(d.b_picks, d.a_picks, counters)
    d.a_score, d.b_score = sa["total"], sb["total"]
    d.detail = {"a": sa["parts"], "b": sb["parts"], "live_counters": bool(counters)}
    a = await session.scalar(select(User).where(User.id == d.a_id).with_for_update().execution_options(populate_existing=True))
    b = await session.scalar(select(User).where(User.id == d.b_id).with_for_update().execution_options(populate_existing=True))
    res = 0.5 if d.a_score == d.b_score else (1.0 if d.a_score > d.b_score else 0.0)
    d.a_delta = elo_delta(a.draft_elo, b.draft_elo, res)
    d.b_delta = -d.a_delta
    a.draft_elo += d.a_delta
    b.draft_elo += d.b_delta
    d.winner_id = None if res == 0.5 else (d.a_id if res == 1.0 else d.b_id)
    d.status = "done"
    win_pts = int(await app_settings.get_value(session, "duel_win_points"))
    lose_pts = int(await app_settings.get_value(session, "duel_lose_points"))
    for u in (a, b):
        pts = lose_pts if d.winner_id not in (None, u.id) else (win_pts if d.winner_id == u.id else lose_pts)
        await arena.add_points(session, u.id, pts, "draft_duel", f"duel:{d.id}:{u.id}")
        delta = d.a_delta if u.id == d.a_id else d.b_delta
        mine, theirs = (d.a_score, d.b_score) if u.id == d.a_id else (d.b_score, d.a_score)
        head = "🏆 G'alaba!" if d.winner_id == u.id else ("🤝 Durang" if d.winner_id is None else "💥 Mag'lubiyat")
        out.user(u.id, f"{head} Draft Jang: {mine} - {theirs}\nDraft ELO: {u.draft_elo} ({delta:+d})", webapp_button("Natija", f"/duel/{d.code}"))
    return d


async def tick(sessions: async_sessionmaker, out: Outbox) -> None:
    async with sessions() as session:
        ids = list(await session.scalars(select(DraftDuel.code).where(DraftDuel.status.in_(("waiting", "picking")), DraftDuel.expires_at <= _now()).limit(100)))
    for code in ids:
        async with sessions() as session:
            async with session.begin():
                d = await _lock(session, code)
                if d.status in ("waiting", "picking") and d.expires_at <= _now():
                    d.status = "expired"


def _hero(hid: int) -> dict:
    h = mlbb.heroes()[hid]
    return {"id": hid, "name": h["name"], "role": h["role"], "lane": h["lane"]}


async def view(session: AsyncSession, code: str, me: int, bot_username: str) -> dict:
    d = await session.scalar(select(DraftDuel).where(DraftDuel.code == code))
    if d is None:
        raise NotFound("Jang")
    ids = [x for x in (d.a_id, d.b_id) if x]
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(ids)))}
    side = "a" if me == d.a_id else ("b" if me == d.b_id else None)
    done = d.status == "done"
    mine = d.a_picks if side == "a" else (d.b_picks if side == "b" else None)
    theirs = (d.b_picks if side == "a" else d.a_picks) if done else None
    u = lambda uid: ({"id": uid, "name": (users[uid].first_name or "O'yinchi")[:24], "elo": users[uid].draft_elo} if uid in users else None)  # noqa: E731
    return {"code": d.code, "status": d.status, "side": side, "opponent": u(d.b_id if side == "a" else d.a_id) if side else u(d.a_id),
            "me": u(me) if side else None, "expires_at": d.expires_at.isoformat(), "link": link(bot_username, d.code),
            "slots": [{"key": s, "label": SLOT_LABEL[s]} for s in SLOTS],
            "my_picks": {s: _hero(h) for s, h in mine.items()} if mine else None,
            "their_picks": {s: _hero(h) for s, h in theirs.items()} if theirs else None,
            "opponent_ready": bool((d.b_picks if side == "a" else d.a_picks)) if side else False,
            "result": {"a_score": d.a_score, "b_score": d.b_score, "winner_id": d.winner_id, "a_delta": d.a_delta, "b_delta": d.b_delta,
                       "detail": d.detail, "a": u(d.a_id), "b": u(d.b_id)} if done else None}


async def top(session: AsyncSession, limit: int = 20) -> list[dict]:
    rows = await session.scalars(select(User).where(User.draft_elo != 1000).order_by(User.draft_elo.desc()).limit(limit))
    return [{"place": i + 1, "name": (u.first_name or "O'yinchi")[:24], "elo": u.draft_elo, "id": u.id} for i, u in enumerate(rows)]
