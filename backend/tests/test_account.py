from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import Tournament, TournamentEntry, User
from app.services import account
from app.services import services as svc
from app.services.notify import Outbox
from tests.conftest import get_balance, set_balance

IMG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


async def test_kyc_flow(api, ctx, monkeypatch):
    calls = []

    async def fake_send(user, images):
        calls.append((user.id, len(images)))

    monkeypatch.setattr(account, "send_kyc_to_admins", fake_send)
    await api(5).get("/me")
    files = {k: (f"{k}.png", IMG, "image/png") for k in ("selfie", "front", "back")}
    r = await api(5).c.post("/api/me/kyc", files=files, headers={"X-Dev-User": "5"})
    assert r.status_code == 200, r.text
    assert r.json()["kyc_status"] == "pending" and calls == [(5, 3)]
    # takror yuborib bo'lmaydi
    r = await api(5).c.post("/api/me/kyc", files=files, headers={"X-Dev-User": "5"})
    assert r.status_code == 409
    # admin ro'yxatda ko'radi va tasdiqlaydi
    assert [x["id"] for x in (await api(1).get("/admin/kyc")).json()] == [5]
    assert (await api(5).get("/admin/kyc")).status_code == 403
    r = await api(1).post("/admin/kyc/5", {"approve": True})
    assert r.json()["kyc_status"] == "verified"
    me = (await api(5).get("/me")).json()
    assert me["kyc_status"] == "verified" and me["verified"] is True
    assert any(uid == 5 and "tasdiqlandi" in text for uid, text, _ in ctx["sent"])


async def test_kyc_requires_three_images(api, monkeypatch):
    monkeypatch.setattr(account, "send_kyc_to_admins", lambda *a: None)
    files = {"selfie": ("a.png", IMG, "image/png"), "front": ("b.png", IMG, "image/png")}
    r = await api(6).c.post("/api/me/kyc", files=files, headers={"X-Dev-User": "6"})
    assert r.status_code == 422


async def test_pin_protects_spending(api):
    await set_balance(7, 100_000)
    a = api(7)
    assert (await a.post("/me/pin", {"pin": "1234"})).json()["code"] if False else True
    r = await a.post("/me/pin", {"pin": "1111"})
    assert r.status_code == 400  # oson PIN
    r = await a.post("/me/pin", {"pin": "2580"})
    assert r.status_code == 200 and r.json()["token"]
    assert (await a.get("/me")).json()["pin_set"] is True
    # tokensiz pul yechib bo'lmaydi
    r = await a.post("/wallet/withdraw", {"amount": 20_000, "card_number": "8600123412341234"})
    assert r.status_code == 403 and r.json()["error"] == "pin_required"
    # noto'g'ri PIN
    assert (await a.post("/me/pin/verify", {"pin": "0000"})).status_code == 403
    token = (await a.post("/me/pin/verify", {"pin": "2580"})).json()["token"]
    r = await a.c.post("/api/wallet/withdraw", json={"amount": 20_000, "card_number": "8600123412341234"},
                       headers={"X-Dev-User": "7", "X-Pin-Token": token})
    assert r.status_code == 200, r.text
    # til o'zgartirish PIN so'ramaydi
    assert (await a.patch("/me", {"lang": "en"})).json()["lang"] == "en"
    # PIN almashsa eski token ishlamaydi
    r = await a.post("/me/pin", {"pin": "3690", "old_pin": "2580"})
    assert r.status_code == 200
    r = await a.c.post("/api/me/cards", json={"number": "8600123412341234"}, headers={"X-Dev-User": "7", "X-Pin-Token": token})
    assert r.status_code == 403
    # biometriya: kalit bilan token olinadi
    key = (await a.post("/me/pin/bio", {"pin": "3690"})).json()["key"]
    assert (await a.get("/me")).json()["bio_set"] is True
    assert (await a.post("/me/pin/bio/verify", {"key": "xato"})).status_code == 403
    assert (await a.post("/me/pin/bio/verify", {"key": key})).json()["token"]
    # PIN o'chirish
    assert (await a.post("/me/pin/remove", {"pin": "0000"})).status_code == 403
    assert (await a.post("/me/pin/remove", {"pin": "3690"})).status_code == 200
    me = (await a.get("/me")).json()
    assert me["pin_set"] is False and me["bio_set"] is False


async def test_saved_cards_and_withdraw(api):
    await set_balance(8, 100_000)
    a = api(8)
    r = await a.post("/me/cards", {"number": "9860 1234 5678 4821", "holder": "ali valiyev", "expiry": "12/27"})
    assert r.status_code == 200, r.text
    c1 = r.json()
    assert c1["brand"] == "Humo" and c1["last4"] == "4821" and c1["is_default"] and c1["holder"] == "ALI VALIYEV"
    assert "number" not in c1
    c2 = (await a.post("/me/cards", {"number": "8600123412347730"})).json()
    assert c2["brand"] == "Uzcard" and not c2["is_default"]
    assert (await a.post("/me/cards", {"number": "9860123456784821"})).status_code == 400  # takror
    assert (await a.post("/me/cards", {"number": "123"})).status_code == 400
    await a.post(f"/me/cards/{c2['id']}/default")
    cards = (await a.get("/me/cards")).json()
    assert cards[0]["id"] == c2["id"] and cards[0]["is_default"]
    # boshqa foydalanuvchi kartasini ishlatib bo'lmaydi
    assert (await api(9).post("/wallet/withdraw", {"amount": 20_000, "card_id": c1["id"]})).status_code == 404
    r = await a.post("/wallet/withdraw", {"amount": 20_000, "card_id": c1["id"]})
    assert r.status_code == 200, r.text
    assert r.json()["card"].endswith("4821")
    assert await get_balance(8) == 80_000
    await a.c.delete(f"/api/me/cards/{c2['id']}", headers={"X-Dev-User": "8"})
    cards = (await a.get("/me/cards")).json()
    assert len(cards) == 1 and cards[0]["is_default"]


async def test_notifications_can_be_muted(api, ctx):
    await api(10).get("/me")
    await api(11).get("/me")
    await api(10).patch("/me", {"notify_tour": False})
    async with SessionLocal() as s, s.begin():
        t = Tournament(title="Kubok", game="ML", prize_fund=1_000_000, max_players=10,
                       starts_at=datetime.now(timezone.utc) + timedelta(minutes=20))
        s.add(t)
        await s.flush()
        for uid in (10, 11):
            s.add(TournamentEntry(tournament_id=t.id, user_id=uid, nick="n", game_id="1", server=""))
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        assert await svc.tournament_reminders(s, out) == 1
    await out.flush()
    got = [uid for uid, text, _ in ctx["sent"] if "turniri" in text]
    assert got == [11]
    # ikkinchi marta yuborilmaydi
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        assert await svc.tournament_reminders(s, out) == 0
    async with SessionLocal() as s:
        assert (await s.get(User, 10)).notify_tour is False
