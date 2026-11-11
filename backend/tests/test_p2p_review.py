from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.db import SessionLocal
from app.models import Topup
from app.services import p2p
from app.services.notify import Outbox
from tests.conftest import get_balance, set_balance

SECRET = {"X-P2P-Secret": "test-secret"}


async def test_cards_paid_auto_and_admin(api, ctx):
    await set_balance(90, 0)
    adm, u = api(1), api(90)
    assert (await adm.post("/admin/p2p-cards", {"number": "123"})).status_code == 400
    c1 = (await adm.post("/admin/p2p-cards", {"number": "8600123412341234", "holder": "vaynexo kassa"})).json()
    await adm.post("/admin/p2p-cards", {"number": "9860 1111 2222 3333", "holder": "x", "active": False})
    assert c1["kind"] == "Uzcard" and c1["number"] == "8600 1234 1234 1234" and c1["holder"] == "VAYNEXO KASSA"
    assert (await u.get("/admin/p2p-cards")).status_code == 403
    t = (await u.post("/wallet/topup", {"amount": 50_000})).json()
    assert [c["number"] for c in t["cards"]] == ["8600 1234 1234 1234"] and t["status"] == "pending"
    # «To'ladim» — chek so'ralmaydi, admin darhol bezovta qilinmaydi
    r = (await u.post(f"/wallet/topup/{t['id']}/paid")).json()
    assert r["status"] == "checking"
    assert not any("tekshiruvi" in text or "bank xabari" in text for _, text, _ in ctx["sent"])
    assert (await u.get("/wallet")).json()["pending_topup"]["status"] == "checking"
    # SMS-forwarder: ?key= bilan, «message» maydoni bilan ham ishlaydi
    sms = f"HUMOCARD *5276: Popolnenie {t['pay_amount']:,}.00 UZS".replace(",", " ")
    r = await u.c.post(f"/api/p2p/incoming?key=wrong", json={"message": sms})
    assert r.status_code == 401
    r = await u.c.post(f"/api/p2p/incoming?key=test-secret", json={"message": sms, "sentStamp": "111"})
    assert r.json()["matched"] is True
    assert await get_balance(90) == t["pay_amount"]
    assert (await adm.post(f"/admin/topups/{t['id']}/confirm")).status_code == 409  # ikki marta tushmaydi
    # oddiy matn ko'rinishidagi tana ham qabul qilinadi
    t2 = (await u.post("/wallet/topup", {"amount": 20_000})).json()
    r = await u.c.post("/api/p2p/incoming", content=f"Kirim: {t2['pay_amount']} UZS".encode(), headers={**SECRET, "content-type": "text/plain"})
    assert r.json()["matched"] is True


async def test_admin_reminded_once_when_no_sms(api, ctx):
    await set_balance(91, 0)
    u, adm = api(91), api(1)
    t = (await u.post("/wallet/topup", {"amount": 20_000})).json()
    await u.post(f"/wallet/topup/{t['id']}/paid")
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        assert await p2p.remind_unmatched(s, out) == 0  # hali erta
        await s.execute(update(Topup).where(Topup.id == t["id"]).values(claimed_at=datetime.now(timezone.utc) - timedelta(minutes=20)))
    async with SessionLocal() as s, s.begin():
        assert await p2p.remind_unmatched(s, out) == 1
    async with SessionLocal() as s, s.begin():
        assert await p2p.remind_unmatched(s, out) == 0  # bir marta
    assert out.items and out.items[0][2]["inline_keyboard"][0][0]["callback_data"] == f"topup:ok:{t['id']}"
    r = (await adm.post(f"/admin/topups/{t['id']}/reject", {"reason": "Pul tushmagan"})).json()
    assert r["status"] == "rejected" and await get_balance(91) == 0
    assert any(uid == 91 and "tasdiqlanmadi" in text for uid, text, _ in ctx["sent"])
    t3 = (await u.post("/wallet/topup", {"amount": 30_000})).json()
    await u.post(f"/wallet/topup/{t3['id']}/paid")
    assert (await adm.post(f"/admin/topups/{t3['id']}/confirm")).json()["status"] == "paid"
    assert await get_balance(91) == t3["pay_amount"]


async def test_sms_setup_and_timer(api):
    d = (await api(1).get("/admin/p2p/sms-setup")).json()
    assert d["ready"] and d["url"].endswith("/api/p2p/incoming") and d["secret"] == "test-secret"
    assert (await api(5).get("/admin/p2p/sms-setup")).status_code == 403
    await api(1).put("/admin/settings", {"key": "topup_timeout_minutes", "value": 15})
    t = (await api(92).post("/wallet/topup", {"amount": 10_000})).json()
    left = (datetime.fromisoformat(t["expires_at"]) - datetime.fromisoformat(t["created_at"])).total_seconds()
    assert 14 * 60 < left <= 15 * 60 + 5


async def test_withdraw_only_earnings_and_wallet_id(api):
    from tests.conftest import give_earnings

    await set_balance(93, 100_000)  # to'ldirilgan pul — yechilmaydi
    u = api(93)
    w = (await u.get("/wallet")).json()
    assert w["withdraw"]["earned"] == 0 and w["withdraw"]["available"] == 0
    assert w["wallet_id"].startswith("VX ") and len(w["wallet_id"].replace(" ", "")) == 10
    assert (await u.get("/me")).json()["wallet_id"] == w["wallet_id"]  # o'zgarmaydi
    r = await u.post("/wallet/withdraw", {"amount": 20_000, "card_number": "8600123412341234"})
    assert r.status_code == 403 and r.json()["error"] == "no_earnings"
    # daromad bor: faqat daromad miqdorigacha
    await give_earnings(94, 50_000)
    async with SessionLocal() as s, s.begin():
        from app.models import User
        (await s.get(User, 94)).balance += 200_000  # + to'ldirilgan pul
    v = api(94)
    assert (await v.get("/wallet")).json()["withdraw"]["available"] == 50_000
    assert (await v.post("/wallet/withdraw", {"amount": 60_000, "card_number": "8600123412341234"})).status_code == 400
    assert (await v.post("/wallet/withdraw", {"amount": 50_000, "card_number": "8600123412341234"})).status_code == 200
    assert (await v.get("/wallet")).json()["withdraw"]["available"] == 0
    # admin hamyon ID bo'yicha topadi
    wid = (await v.get("/me")).json()["wallet_id"]
    found = (await api(1).get(f"/admin/users?q={wid.replace(' ', '%20')}")).json()
    assert [x["id"] for x in found] == [94]
