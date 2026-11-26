"""Odat: kunlik check-in + seriya, «Bugungi qahramon», haftalik Meta bashorat."""

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, BadState
from app.models import MetaPick, MetaWeek, User
from app.services import app_settings, arena, mlbb

MILESTONES = {3: 10, 7: 30, 14: 60, 30: 150}  # ketma-ket kun -> qo'shimcha ball


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _yesterday() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d")


def hero_of_day(day: str | None = None) -> dict:
    day = day or _today()
    ids = sorted(mlbb.heroes())
    hid = ids[random.Random(f"hod:{day}").randrange(len(ids))]
    h = mlbb.heroes()[hid]
    return {"id": hid, "name": h["name"], "role": h["role"], "lane": h["lane"]}


def next_milestone(streak: int) -> dict | None:
    for d, pts in MILESTONES.items():
        if streak < d:
            return {"days": d, "points": pts, "left": d - streak}
    return None


async def status(session: AsyncSession, user: User) -> dict:
    today = _today()
    done = user.streak_last == today
    alive = user.streak_last in (today, _yesterday())
    streak = user.streak_days if alive else 0
    return {"streak": streak, "done_today": done, "hero": hero_of_day(), "points": int(await app_settings.get_value(session, "checkin_points")),
            "next": next_milestone(streak)}


async def checkin(session: AsyncSession, user_id: int) -> dict:
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    today = _today()
    if user.streak_last == today:
        raise BadState("Bugun belgilangan")
    user.streak_days = (user.streak_days + 1) if user.streak_last == _yesterday() else 1
    user.streak_last = today
    base = int(await app_settings.get_value(session, "checkin_points"))
    bonus = MILESTONES.get(user.streak_days, 0)
    if base + bonus > 0:
        await arena.add_points(session, user_id, base + bonus, "checkin", f"checkin:{user_id}:{today}")
    return {**(await status(session, user)), "earned": base + bonus, "bonus": bonus}


# ---------------------------------------------------------------- Meta bashorat
def week_key() -> str:
    return arena.period_of("weekly")


async def _snapshot(rank: str = "all") -> dict[str, float]:
    from app.services import mlstats

    return {str(x["hero"]): x["win"] for x in await mlstats.rank_stats(rank, 7) if x["pick"] >= 0.05}


async def ensure_week(session: AsyncSession) -> MetaWeek | None:
    """Hafta boshidagi g'alaba foizlari suratini bir marta saqlaydi (jonli statistika bo'lsa)."""
    wk = week_key()
    row = await session.get(MetaWeek, wk)
    if row is not None:
        return row
    try:
        snap = await _snapshot()
    except Exception:  # noqa: BLE001
        return None
    if not snap:
        return None
    row = MetaWeek(week=wk, snapshot=snap)
    session.add(row)
    await session.flush()
    return row


async def meta_state(session: AsyncSession, user_id: int) -> dict:
    wk = week_key()
    row = await ensure_week(session)
    pick = await session.scalar(select(MetaPick).where(MetaPick.user_id == user_id, MetaPick.week == wk))
    prev = await session.scalar(select(MetaWeek).where(MetaWeek.result.is_not(None)).order_by(MetaWeek.week.desc()).limit(1))
    heroes = mlbb.heroes()
    cands = []
    if row:  # nomzodlar: statistikasi bor barcha qahramonlar (alifbo tartibida)
        cands = sorted(({"id": int(h), "name": heroes[int(h)]["name"], "role": heroes[int(h)]["role"], "win": w}
                        for h, w in row.snapshot.items() if int(h) in heroes), key=lambda x: x["name"])
    last = None
    if prev and prev.result:
        wid = int(prev.result["winner"])
        mine = await session.scalar(select(MetaPick).where(MetaPick.user_id == user_id, MetaPick.week == prev.week))
        last = {"week": prev.week, "winner": {"id": wid, "name": heroes.get(wid, {}).get("name", ""), "delta": prev.result.get("delta")},
                "my_hero": mine.hero_id if mine else None, "correct": bool(mine and mine.hero_id == wid)}
    return {"week": wk, "available": bool(row), "points": int(await app_settings.get_value(session, "meta_points")),
            "my_pick": pick.hero_id if pick else None, "candidates": cands, "last": last}


async def meta_pick(session: AsyncSession, user_id: int, hero_id: int) -> dict:
    row = await ensure_week(session)
    if row is None:
        raise BadState("Hozircha jonli statistika yo'q")
    if str(hero_id) not in row.snapshot:
        raise AppError("bad_hero", "Bu qahramonni tanlab bo'lmaydi")
    wk = week_key()
    if await session.scalar(select(MetaPick.id).where(MetaPick.user_id == user_id, MetaPick.week == wk)):
        raise BadState("Bu hafta tanlov qilingan")
    session.add(MetaPick(user_id=user_id, week=wk, hero_id=hero_id))
    await session.flush()
    return await meta_state(session, user_id)


async def settle(session: AsyncSession, out) -> int:
    """O'tgan haftani yopadi: g'alaba foizi eng ko'p oshgan qahramon topiladi, to'g'ri topganlarga ball."""
    wk = week_key()
    old = list(await session.scalars(select(MetaWeek).where(MetaWeek.week < wk, MetaWeek.result.is_(None)).limit(3)))
    n = 0
    for row in old:
        try:
            now = await _snapshot()
        except Exception:  # noqa: BLE001
            continue
        deltas = {h: round(now[h] - w, 2) for h, w in row.snapshot.items() if h in now}
        if not deltas:
            continue
        win = max(deltas, key=lambda h: deltas[h])
        row.result = {"winner": int(win), "delta": deltas[win]}
        pts = int(await app_settings.get_value(session, "meta_points"))
        for p in await session.scalars(select(MetaPick).where(MetaPick.week == row.week, MetaPick.hero_id == int(win))):
            await arena.add_points(session, p.user_id, pts, "meta", f"meta:{row.week}:{p.user_id}")
            name = mlbb.heroes().get(int(win), {}).get("name", "")
            from app.services.notify import webapp_button

            out.user(p.user_id, f"🔮 Meta bashorat to'g'ri chiqdi! {name} +{deltas[win]}% ga o'sdi. +{pts} ball.", webapp_button("Arena", "/arena"))
            n += 1
    return n
