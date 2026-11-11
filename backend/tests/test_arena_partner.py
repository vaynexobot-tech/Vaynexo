from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.db import SessionLocal
from app.models import PartnerVideo, Tournament, User
from tests.conftest import get_balance, set_balance


async def _points(uid: int) -> int:
    async with SessionLocal() as s:
        return (await s.get(User, uid)).points


async def _tournament(fee: int = 10_000) -> int:
    async with SessionLocal() as s, s.begin():
        t = Tournament(title="Kubok", game="ML", prize_fund=1_000_000, entry_fee=fee, max_players=10,
                       starts_at=datetime.now(timezone.utc) + timedelta(days=1))
        s.add(t)
        await s.flush()
        return t.id


async def test_missions_points_and_exchange(api):
    await set_balance(80, 100_000)
    a = api(80)
    m = (await a.get("/arena/missions")).json()
    login = next(x for x in m["daily"] if x["key"] == "login")
    assert login["progress"] == 1 and not login["claimed"]
    assert (await a.post("/arena/missions/invite/claim")).status_code == 409  # bajarilmagan
    assert (await a.post("/arena/missions/login/claim")).json()["reward"] == 10
    assert (await a.post("/arena/missions/login/claim")).status_code == 409  # ikkinchi marta yo'q
    # turnirga yozilish: +20 ball, vazifalar oshadi, xizmat vazifasi ham
    tid = await _tournament()
    r = await a.post(f"/tournaments/{tid}/join", {"nick": "Ali", "game_id": "123"})
    assert r.status_code == 200, r.text
    assert await _points(80) == 30
    m = (await a.get("/arena/missions")).json()
    assert next(x for x in m["daily"] if x["key"] == "join_tournament")["progress"] == 1
    assert next(x for x in m["weekly"] if x["key"] == "play_3")["progress"] == 1
    assert next(x for x in m["weekly"] if x["key"] == "any_service")["progress"] == 1
    # almashtirish: ball yetmaydi
    assert (await a.post("/arena/exchange/free_tournament")).status_code == 400
    async with SessionLocal() as s, s.begin():
        await s.execute(update(User).where(User.id == 80).values(points=2_000))
    r = (await a.post("/arena/exchange/free_tournament")).json()
    assert r["points"] == 500 and r["passes"] == 1
    # pass bilan bepul kirish
    tid2 = await _tournament(50_000)
    bal = await get_balance(80)
    assert (await a.post(f"/tournaments/{tid2}/join", {"nick": "Ali", "game_id": "123", "use_pass": True})).status_code == 200
    assert await get_balance(80) == bal
    r = (await a.post("/arena/exchange/boost_discount")).json()
    assert r["boost_coupon_percent"] == 5 and r["points"] == 20  # 500 + 20 (turnir) - 500


async def test_boost_coupon_and_vip_credit(api):
    await set_balance(81, 1_000_000)
    async with SessionLocal() as s, s.begin():
        await s.execute(update(User).where(User.id == 81).values(boost_coupon_percent=10))
    body = {"current_rank": "Epic", "target_rank": "Legend", "login_method": "telegram"}
    q = (await api(81).post("/boost/quote", body)).json()
    o = (await api(81).post("/boost/orders", body)).json()
    assert o["price"] == q["price"] - q["price"] * 10 // 100
    async with SessionLocal() as s:
        assert (await s.get(User, 81)).boost_coupon_percent == 0


async def test_prediction_and_leaderboard(api, ctx):
    a1 = (await api(1).post("/admin/arena/matches", {"title": "Final", "team_a": "Lions", "team_b": "Wolves",
                                                       "starts_at": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()})).json()
    assert (await api(82).get("/arena/summary")).json()["prediction"]["id"] == a1["id"]
    assert (await api(82).post(f"/arena/predictions/{a1['id']}", {"pick": "a"})).status_code == 200
    assert (await api(82).post(f"/arena/predictions/{a1['id']}", {"pick": "b"})).status_code == 409
    await api(83).post(f"/arena/predictions/{a1['id']}", {"pick": "b"})
    r = await api(1).post(f"/admin/arena/matches/{a1['id']}/settle", {"result": "a"})
    assert r.json()["winners"] == 1
    assert await _points(82) == 50 and await _points(83) == 0
    assert (await api(1).post(f"/admin/arena/matches/{a1['id']}/settle", {"result": "a"})).status_code == 409
    lb = (await api(83).get("/arena/leaderboard")).json()
    assert lb["items"][0]["user_id"] == 82 and lb["items"][0]["points"] == 50 and lb["season"]["number"] >= 1
    assert lb["me"]["points"] == 0


async def test_team_posts(api, ctx):
    a = api(84)
    p = (await a.post("/arena/team-posts", {"kind": "player", "name": "aziz_gg", "lane": "Gold", "rank": "Mythic 34★"})).json()
    assert p["mine"]
    assert (await a.post("/arena/team-posts", {"kind": "x", "name": "a"})).status_code == 422
    feed = (await api(85).get("/arena/team-posts?lane=Gold")).json()
    assert [x["id"] for x in feed] == [p["id"]] and not feed[0]["mine"]
    assert (await api(85).post(f"/arena/team-posts/{p['id']}/contact")).status_code == 200
    assert any(uid == 84 and "Jamoa topish" in text for uid, text, _ in ctx["sent"])
    assert (await a.post(f"/arena/team-posts/{p['id']}/contact")).status_code == 409


async def test_partner_flow(api, ctx):
    a = api(86)
    r = await a.post("/partner/videos", {"url": "https://www.tiktok.com/@aziz/video/7431?is_from=webapp"})
    assert r.status_code == 200, r.text
    v = r.json()
    assert v["platform"] == "tiktok" and v["url"] == "https://tiktok.com/@aziz/video/7431"
    assert (await a.post("/partner/videos", {"url": "https://example.com/v/1"})).status_code == 400
    # 2 kunda 1 ta
    assert (await a.post("/partner/videos", {"url": "https://youtu.be/abcdef"})).status_code == 409
    # takror havola boshqa odamdan ham qabul qilinmaydi
    assert (await api(87).post("/partner/videos", {"url": "tiktok.com/@aziz/video/7431"})).status_code == 409
    # admin: layk nisbati past -> tasdiqlab bo'lmaydi
    assert (await api(1).post(f"/admin/partner/videos/{v['id']}", {"approve": True, "views": 12_400, "likes": 100})).status_code == 409
    r = (await api(1).post(f"/admin/partner/videos/{v['id']}", {"approve": True, "views": 12_400, "likes": 900})).json()
    assert r["status"] == "approved" and r["tier"] == 2
    async with SessionLocal() as s:
        assert (await s.get(User, 86)).tournament_passes == 4
    o = (await a.get("/partner")).json()
    assert o["stats"]["views"] == 12_400 and o["tiers"][1]["done"] and not o["tiers"][2]["done"]
    # interval o'tgach yana yuborish mumkin
    async with SessionLocal() as s, s.begin():
        await s.execute(update(PartnerVideo).values(created_at=datetime.now(timezone.utc) - timedelta(days=3)))
    assert (await a.post("/partner/videos", {"url": "https://youtu.be/abcdef"})).status_code == 200


async def test_kyc_required_for_market_and_rent(api, monkeypatch):
    from dataclasses import replace

    from app.services import app_settings as A
    from tests.test_flows import LISTING

    monkeypatch.setitem(A.SCHEMA, "kyc_marketplace", replace(A.SCHEMA["kyc_marketplace"], default="on"))
    r = await api(88).post("/listings", LISTING)
    assert r.status_code == 403 and r.json()["error"] == "kyc_required"
    async with SessionLocal() as s, s.begin():
        await s.execute(update(User).where(User.id == 88).values(kyc_status="verified"))
    assert (await api(88).post("/listings", LISTING)).status_code == 200
