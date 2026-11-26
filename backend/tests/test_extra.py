from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.db import SessionLocal
from app.models import DraftDuel, DonateOrder, MetaWeek, Split, User
from app.services import duel, habit, mlbb, split
from app.services.notify import Outbox
from tests.conftest import get_balance, make_package, set_balance

ML = {"player_id": "123456789", "zone_id": "1234"}


def _now():
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------- Birgalikda to'laymiz / Orzu
async def test_split_flow_complete_and_order(api, ctx):
    pid = await make_package(40_000)
    for u in (10, 11, 12):
        await set_balance(u, 100_000)
    r = await api(10).post("/split", {"mode": "split", "package_id": pid, **ML})
    assert r.status_code == 200, r.text
    code = r.json()["code"]
    assert r.json()["target"] == 40_000 and r.json()["is_creator"]
    assert (await api(11).get(f"/split/{code}")).json()["game_id"] is None  # ID faqat yaratuvchiga
    r = await api(11).post(f"/split/{code}/pay", {"amount": 15_000})
    assert r.json()["collected"] == 15_000 and await get_balance(11) == 85_000
    assert (await api(11).post(f"/split/{code}/pay", {"amount": 500})).status_code == 400  # kam
    r = await api(12).post(f"/split/{code}/pay", {"amount": 99_000})  # ortig'i olinmaydi
    assert r.json()["collected"] == 40_000 and r.json()["status"] == "done"
    assert await get_balance(12) == 100_000 - 25_000
    async with SessionLocal() as s:
        o = await s.get(DonateOrder, (await api(10).get(f"/split/{code}")).json()["order_id"])
        assert o.user_id == 10 and o.player_id == "123456789" and o.price == 40_000
    assert any(j[0] == "fulfil_donate" for j in ctx["jobs"])
    assert await get_balance(10) == 100_000  # yaratuvchi hech narsa to'lamadi
    assert (await api(11).post(f"/split/{code}/pay", {"amount": 5_000})).status_code == 409  # yakunlangan


async def test_split_expiry_refunds_everyone(api):
    pid = await make_package(40_000)
    for u in (10, 11):
        await set_balance(u, 100_000)
    code = (await api(10).post("/split", {"mode": "wish", "package_id": pid, **ML})).json()["code"]
    await api(11).post(f"/split/{code}/pay", {"amount": 10_000})
    await api(10).post(f"/split/{code}/pay", {"amount": 5_000})
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Split).where(Split.code == code).values(expires_at=_now() - timedelta(minutes=1)))
    out = Outbox()
    await split.tick(SessionLocal, out)
    assert await get_balance(11) == 100_000 and await get_balance(10) == 100_000
    assert (await api(10).get(f"/split/{code}")).json()["status"] == "expired"
    await split.tick(SessionLocal, out)  # takror — ikki marta qaytmaydi
    assert await get_balance(11) == 100_000


async def test_split_cancel_only_creator(api):
    pid = await make_package(40_000)
    for u in (10, 11):
        await set_balance(u, 50_000)
    code = (await api(10).post("/split", {"mode": "split", "package_id": pid, **ML})).json()["code"]
    await api(11).post(f"/split/{code}/pay", {"amount": 20_000})
    assert (await api(11).post(f"/split/{code}/cancel")).status_code == 403
    r = await api(10).post(f"/split/{code}/cancel")
    assert r.json()["status"] == "cancelled" and await get_balance(11) == 50_000


# ---------------------------------------------------------------- Draft Jang
GOOD = {"gold": 0, "exp": 0, "mid": 0, "jungle": 0, "roam": 0}


def _team(*lanes_roles):
    """Berilgan liniya bo'yicha mos qahramonlar (har xil)."""
    heroes = mlbb.heroes()
    picks, used = {}, set()
    for lane in ("gold", "exp", "mid", "jungle", "roam"):
        h = next(h for h in sorted(heroes.values(), key=lambda x: x["id"]) if h["lane"] == lane and h["id"] not in used)
        picks[lane] = h["id"]
        used.add(h["id"])
    return picks


async def test_score_and_elo_math():
    good = _team()
    s = duel.score_draft(good, good)
    assert s["parts"]["lane"] == 40 and s["total"] >= 40
    assert duel.elo_delta(1000, 1000, 1.0) == 12 and duel.elo_delta(1000, 1000, 0.0) == -12 and duel.elo_delta(1000, 1000, 0.5) == 0
    with_c = duel.score_draft(good, good, {h: set(good.values()) for h in good.values()})
    assert with_c["parts"]["counter"] == 25


async def test_duel_full_flow(api, monkeypatch):
    async def no_counters(ids):
        return {}

    monkeypatch.setattr(duel, "_live_counters", no_counters)
    for u in (10, 11):
        await set_balance(u, 0)
    code = (await api(10).post("/duel")).json()["code"]
    assert (await api(11).post(f"/duel/{code}/join")).json()["status"] == "picking"
    await set_balance(12, 0)
    assert (await api(12).post(f"/duel/{code}/join")).status_code == 409  # uchinchi o'yinchi qo'shila olmaydi
    team = _team()
    r = await api(10).post(f"/duel/{code}/picks", {"picks": team})
    assert r.status_code == 200 and r.json()["result"] is None and r.json()["my_picks"]["gold"]["id"] == team["gold"]
    assert (await api(11).get(f"/duel/{code}")).json()["their_picks"] is None  # ko'r draft
    assert (await api(10).post(f"/duel/{code}/picks", {"picks": team})).status_code == 409
    dup = {**team, "exp": team["gold"]}
    assert (await api(11).post(f"/duel/{code}/picks", {"picks": dup})).status_code == 400
    ids = [h["id"] for h in sorted(mlbb.heroes().values(), key=lambda x: x["id"]) if h["role"] == "mage"][:5]
    weak = dict(zip(team, ids))
    r = await api(11).post(f"/duel/{code}/picks", {"picks": weak})
    assert r.status_code == 200 and r.json()["result"]["winner_id"] == 10
    async with SessionLocal() as s:
        assert (await s.get(User, 10)).draft_elo == 1012 and (await s.get(User, 11)).draft_elo == 988
    top = (await api(10).get("/duel/top")).json()["items"]
    assert top[0]["id"] == 10 and top[0]["elo"] == 1012
    assert (await api(10).get(f"/duel/{code}")).json()["their_picks"]["gold"]["id"] == weak["gold"]


async def test_duel_expires():
    await set_balance(10, 0)
    async with SessionLocal() as s, s.begin():
        d = await duel.create(s, 10)
        code = d.code
    async with SessionLocal() as s, s.begin():
        await s.execute(update(DraftDuel).where(DraftDuel.code == code).values(expires_at=_now() - timedelta(minutes=1)))
    await duel.tick(SessionLocal, Outbox())
    async with SessionLocal() as s:
        from sqlalchemy import select

        assert (await s.scalar(select(DraftDuel.status).where(DraftDuel.code == code))) == "expired"


# ---------------------------------------------------------------- Seriya va Meta
async def test_checkin_streak_and_milestone(api):
    await set_balance(30, 0)
    r = await api(30).post("/habit/checkin")
    assert r.json()["streak"] == 1 and r.json()["earned"] == 5 and r.json()["done_today"]
    assert (await api(30).post("/habit/checkin")).status_code == 409
    async with SessionLocal() as s, s.begin():  # kecha belgilagan, 2 kunlik seriya
        yday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y%m%d")
        await s.execute(update(User).where(User.id == 30).values(streak_last=yday, streak_days=2))
    r = await api(30).post("/habit/checkin")
    assert r.json()["streak"] == 3 and r.json()["bonus"] == 10 and r.json()["earned"] == 15
    async with SessionLocal() as s, s.begin():  # 3 kun o'tkazib yubordi — seriya uzildi
        old = (datetime.now(timezone.utc) - timedelta(days=4)).strftime("%Y%m%d")
        await s.execute(update(User).where(User.id == 30).values(streak_last=old, streak_days=3))
    assert (await api(30).get("/habit")).json()["streak"] == 0
    assert (await api(30).post("/habit/checkin")).json()["streak"] == 1
    assert habit.hero_of_day("20261126") == habit.hero_of_day("20261126")


async def test_meta_pick_and_settle(api, monkeypatch):
    from app.services import mlstats

    h1, h2 = sorted(mlbb.heroes())[:2]

    async def snap1(rank="all", days=7):
        return [{"hero": h1, "win": 50.0, "pick": 1.0}, {"hero": h2, "win": 50.0, "pick": 1.0}]

    monkeypatch.setattr(mlstats, "rank_stats", snap1)
    await set_balance(31, 0)
    await set_balance(32, 0)
    st = (await api(31).get("/meta")).json()
    assert st["available"] and len(st["candidates"]) == 2
    assert (await api(31).post("/meta/pick", {"hero_id": h1})).json()["my_pick"] == h1
    assert (await api(31).post("/meta/pick", {"hero_id": h2})).status_code == 409
    await api(32).post("/meta/pick", {"hero_id": h2})
    # hafta o'tdi: h2 ko'tarildi
    async with SessionLocal() as s, s.begin():
        await s.execute(update(MetaWeek).values(week="2020W01"))
        from app.models import MetaPick

        await s.execute(update(MetaPick).values(week="2020W01"))

    async def snap2(rank="all", days=7):
        return [{"hero": h1, "win": 49.0, "pick": 1.0}, {"hero": h2, "win": 53.0, "pick": 1.0}]

    monkeypatch.setattr(mlstats, "rank_stats", snap2)
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        assert await habit.settle(s, out) == 1
    async with SessionLocal() as s:
        assert (await s.get(User, 32)).points == 50 and (await s.get(User, 31)).points == 0
    async with SessionLocal() as s, s.begin():
        assert await habit.settle(s, out) == 0  # ikki marta emas


async def test_player_card_image_and_send(api, monkeypatch):
    from app.config import settings
    from app.services import card

    png = card.player_card_png("Aziz", "mythic", "gold", [109, 4, 9], "Jangchi", 620, 1012, 3, 47, "https://t.me/x?startapp=ref_1")
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 10_000
    monkeypatch.setattr(settings, "bot_username", "vaynexobot")
    sent = []

    class FakeBot:
        async def send_photo(self, chat_id, photo, caption=None):
            sent.append((chat_id, caption))

    import app.bot.instance as inst

    monkeypatch.setattr(inst, "get_bot", lambda: FakeBot())
    await set_balance(30, 0)
    assert (await api(30).post("/arena/card")).status_code == 200 and "ref_30" in sent[0][1]
