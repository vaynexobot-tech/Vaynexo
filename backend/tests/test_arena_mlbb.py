from sqlalchemy import select

from app.db import SessionLocal
from app.models import User
from app.services import mlbb
from tests.conftest import set_balance


async def test_profile_save_and_validation(api):
    await set_balance(5, 0)
    r = await api(5).put("/arena/profile", {"nick": "Zed", "lane": "jungle", "rank": "mythic", "heroes": [109, 109, 9, 99999, 1, 4]})
    assert r.status_code == 200, r.text
    assert r.json()["heroes"] == [109, 9, 1] and r.json()["rank"] == "mythic"
    assert (await api(5).put("/arena/profile", {"lane": "top"})).status_code == 400
    assert (await api(5).get("/arena/profile")).json()["nick"] == "Zed"


async def test_quiz_flow_points_and_no_double_answer(api):
    await set_balance(6, 0)
    q = (await api(6).get("/arena/quiz")).json()
    assert len(q["questions"]) == 5 and not q["done"]
    assert all("answer" not in x for x in q["questions"])  # javob oldindan berilmaydi
    assert q["questions"][0]["type"] == "who" and len(q["questions"][0]["options"]) == 4
    assert q["questions"][4]["type"] == "role" and q["questions"][4]["name"]
    # to'g'ri javobni serverdagi kabi hisoblaymiz
    right = mlbb.question(6, mlbb.today(), 0)["answer"]
    r = (await api(6).post("/arena/quiz/0", {"answer": right})).json()
    assert r["correct"] and r["points"] == 10
    assert (await api(6).post("/arena/quiz/0", {"answer": right})).status_code == 409
    r = (await api(6).post("/arena/quiz/1", {"answer": "noto'g'ri"})).json()
    assert r["correct"] is False and r["points"] == 0
    async with SessionLocal() as s:
        assert (await s.get(User, 6)).points == 10
    q = (await api(6).get("/arena/quiz")).json()
    assert q["questions"][0]["answer"] == right and q["score"] == 1
    # savollar bir kunda takrorlanmaydi
    heroes = {mlbb.question(6, mlbb.today(), n)["hero"] for n in range(5)}
    assert len(heroes) == 5


async def test_hero_vote_once_per_week(api):
    await set_balance(7, 0)
    await set_balance(8, 0)
    r = (await api(7).post("/arena/hero-vote", {"hero_id": 109})).json()
    assert r["my"] == 109 and r["earned"] == 5 and r["top"][0] == {"hero": 109, "votes": 1, "pct": 100}
    assert (await api(7).post("/arena/hero-vote", {"hero_id": 9})).status_code == 409
    assert (await api(8).post("/arena/hero-vote", {"hero_id": 424242})).status_code == 404
    await api(8).post("/arena/hero-vote", {"hero_id": 9})
    r = (await api(8).get("/arena/hero-vote")).json()
    assert r["total"] == 2 and r["my"] == 9


async def test_team_post_with_heroes_and_leaderboard_card(api):
    await set_balance(9, 0)
    await api(9).put("/arena/profile", {"nick": "Pro", "lane": "gold", "rank": "glory", "heroes": [1]})
    r = await api(9).post("/arena/team-posts", {"kind": "player", "name": "Pro", "lane": "Gold", "heroes": [1, 2, 3, 4]})
    assert r.status_code == 200 and r.json()["heroes"] == [1, 2, 3]
    lst = (await api(5).get("/arena/team-posts")).json()
    assert lst[0]["author_rank"] == "glory"
    right = mlbb.question(9, mlbb.today(), 0)["answer"]
    await api(9).post("/arena/quiz/0", {"answer": right})
    lb = (await api(9).get("/arena/leaderboard")).json()
    row = next(x for x in lb["items"] if x["user_id"] == 9)
    assert row["hero"] == 1 and row["rank"] == "glory" and row["name"] == "Pro"


async def test_partner_code_flow(api, ctx):
    from app.db import SessionLocal
    from app.models import PartnerVideo
    from app.services import wallet

    await set_balance(20, 0)
    await set_balance(21, 0)
    assert (await api(20).post("/partner/code", {"code": "AZIZ"})).status_code == 409  # tasdiqlangan video yo'q
    async with SessionLocal() as s, s.begin():
        s.add(PartnerVideo(user_id=20, platform="tiktok", url="https://tiktok.com/@a/video/1", status="approved", views=5000, reviewed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc)))
    r = await api(20).post("/partner/code", {"code": "aziz-1"})
    assert r.status_code == 200 and r.json()["code"] == "AZIZ-1" and r.json()["bonus"] == 3000
    assert (await api(20).post("/partner/code", {"code": "BOSHQA"})).status_code == 409
    assert (await api(20).post("/wallet/promo", {"code": "AZIZ-1"})).status_code == 400  # o'zinikini ishlata olmaydi
    async with SessionLocal() as s, s.begin():
        await wallet.credit(s, 21, 10_000, "topup", "t:21")
    r = await api(21).post("/wallet/promo", {"code": "aziz-1"})
    assert r.status_code == 200 and r.json()["amount"] == 3000
    async with SessionLocal() as s:
        assert (await s.get(User, 20)).points == 50
    assert any(uid == 20 and "AZIZ-1" in txt for uid, txt, _ in ctx["sent"])
    ov = (await api(20).get("/partner")).json()
    assert ov["code"]["uses"] == 1 and ov["leaderboard"][0]["views"] == 5000 and ov["ideas"]


async def test_admin_arena_stats_and_web_link(api, client):
    await set_balance(1, 0)
    await set_balance(30, 0)
    await api(30).post("/arena/hero-vote", {"hero_id": 5})
    d = (await api(1).get("/admin/arena/stats")).json()
    assert d["votes_week"] == 1 and d["top_heroes"][0]["hero"] == 5
    assert (await api(30).get("/admin/arena/stats")).status_code == 403
    # kompyuter uchun havola: token bilan admin so'rovlari ishlaydi, oddiy foydalanuvchi tokeni ishlamaydi
    r = (await api(1).post("/admin/web-link")).json()
    token = r["url"].split("#wt=")[1]
    me = await client.get("/api/me", headers={"Authorization": f"web {token}"})
    assert me.status_code == 200 and me.json()["id"] == 1
    assert (await client.get("/api/admin/stats", headers={"Authorization": f"web {token}"})).status_code == 200
    from app.security import make_web_token

    assert (await client.get("/api/me", headers={"Authorization": f"web {make_web_token(30)}"})).status_code == 401
    assert (await client.get("/api/me", headers={"Authorization": f"web {token[:-2]}xx"})).status_code == 401
    assert (await api(30).post("/admin/web-link")).status_code == 403


async def test_ml_account_link(api, monkeypatch):
    from app.services import donate_catalog

    class P:
        async def check_player(self, game, pid, zone):
            return None if pid == "11111" else "ZedUz"

    async def fake(session, g):
        return P()

    monkeypatch.setattr(donate_catalog, "provider_for_game", fake)
    await set_balance(40, 0)
    assert (await api(40).post("/arena/link", {"ml_id": "12ab", "server": "1"})).status_code == 400
    assert (await api(40).post("/arena/link", {"ml_id": "11111", "server": "2463"})).status_code == 400
    r = await api(40).post("/arena/link", {"ml_id": "123456789", "server": "2463"})
    assert r.status_code == 200 and r.json()["verified"] and r.json()["nick"] == "ZedUz" and r.json()["server"] == "2463"
