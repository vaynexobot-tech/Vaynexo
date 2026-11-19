from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import Tournament, User
from tests.conftest import set_balance


async def _tour(fmt="solo", fee=0):
    async with SessionLocal() as s, s.begin():
        t = Tournament(title="Kubok", game="ML", prize_fund=100_000, entry_fee=fee, max_players=16, format=fmt,
                       starts_at=datetime.now(timezone.utc) + timedelta(days=1), status="open")
        s.add(t)
    return t.id


async def test_solo_bracket_with_byes_and_final(api, ctx):
    tid = await _tour()
    ids = [100, 101, 102, 103, 104]
    for u in ids:
        await set_balance(u, 0)
        assert (await api(u).post(f"/tournaments/{tid}/join", {"nick": f"N{u}", "game_id": "123456"})).status_code == 200
    await set_balance(1, 0)
    b = (await api(1).post(f"/admin/tournaments/{tid}/bracket")).json()
    assert [r["name"] for r in b["rounds"]] == ["Chorak final", "Yarim final", "Final"] and b["entries"] == 5
    r1 = b["rounds"][0]["matches"]
    assert len(r1) == 4 and sum(1 for m in r1 if m["b"] is None) == 3  # 8 o'rin, 3 tasi avtomatik o'tadi
    assert (await api(1).post(f"/admin/tournaments/{tid}/bracket")).status_code == 409
    # natijalarni kiritib finalgacha
    for _ in range(10):
        b = (await api(1).get(f"/tournaments/{tid}/bracket")).json()
        todo = [m for r in b["rounds"] for m in r["matches"] if m["a"] and m["b"] and not m["winner"]]
        if not todo:
            break
        m = todo[0]
        assert (await api(1).post(f"/admin/tournaments/matches/{m['id']}/winner", {"entry_id": m["a"]["entry_id"]})).status_code == 200
    b = (await api(100).get(f"/tournaments/{tid}/bracket")).json()
    assert b["champion"] is not None
    async with SessionLocal() as s:
        assert (await s.get(Tournament, tid)).status == "finished"
    assert any("g'alaba qozondingiz" in txt for _, txt, _ in ctx["sent"])
    m = b["rounds"][-1]["matches"][0]
    assert (await api(1).post(f"/admin/tournaments/matches/{m['id']}/winner", {"entry_id": m["a"]["entry_id"]})).status_code == 409


async def test_team_tournament_registration(api):
    tid = await _tour("team", fee=10_000)
    for u in range(110, 116):
        await set_balance(u, 50_000)
        await api(u).put("/arena/profile", {"nick": f"P{u}", "rank": "mythic"})
    assert (await api(110).post(f"/tournaments/{tid}/join", {"nick": "", "game_id": ""})).status_code == 409  # jamoasiz
    team = (await api(110).post("/arena/teams", {"name": "Lions", "tag": "LNS"})).json()["team"]
    assert (await api(110).post(f"/tournaments/{tid}/join", {})).status_code == 409  # 1 kishi < 5
    for u in range(111, 115):
        await api(u).post(f"/arena/teams/{team['id']}/join")
    for r in (await api(110).get("/arena/teams/my")).json()["requests"]:
        await api(110).post(f"/arena/requests/{r['id']}", {"accept": True})
    assert (await api(111).post(f"/tournaments/{tid}/join", {})).status_code == 409  # sardor emas
    r = await api(110).post(f"/tournaments/{tid}/join", {})
    assert r.status_code == 200, r.text
    assert r.json()["format"] == "team" and r.json()["joined"]
    async with SessionLocal() as s:
        assert (await s.get(User, 110)).balance == 40_000
    assert (await api(110).post(f"/tournaments/{tid}/join", {})).status_code == 409
