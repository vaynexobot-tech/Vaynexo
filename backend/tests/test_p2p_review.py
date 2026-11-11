from app.api import wallet as wallet_api
from tests.conftest import get_balance, set_balance

IMG = b"\x89PNG\r\n\x1a\n" + b"0" * 100


async def test_cards_from_admin_and_paid_review(api, ctx, monkeypatch):
    notified = []

    async def fake_notify(t, user, image):
        notified.append((t.id, image is not None))

    monkeypatch.setattr(wallet_api, "_notify_review", fake_notify)
    await set_balance(90, 0)
    adm, u = api(1), api(90)
    # admin kartalar qo'shadi: foydalanuvchi faqat faollarini ko'radi
    assert (await adm.post("/admin/p2p-cards", {"number": "123"})).status_code == 400
    c1 = (await adm.post("/admin/p2p-cards", {"number": "8600123412341234", "holder": "vaynexo kassa"})).json()
    await adm.post("/admin/p2p-cards", {"number": "9860 1111 2222 3333", "holder": "x", "active": False})
    assert c1["kind"] == "Uzcard" and c1["number"] == "8600 1234 1234 1234" and c1["holder"] == "VAYNEXO KASSA"
    assert (await u.get("/admin/p2p-cards")).status_code == 403
    t = (await u.post("/wallet/topup", {"amount": 50_000})).json()
    assert [c["number"] for c in t["cards"]] == ["8600 1234 1234 1234"] and t["status"] == "pending"
    assert 50_000 < t["pay_amount"] < 51_000
    # «To'ladim» + chek -> tekshiruv
    r = await u.c.post(f"/api/wallet/topup/{t['id']}/paid", files={"receipt": ("c.png", IMG, "image/png")}, headers={"X-Dev-User": "90"})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "checking" and r.json()["has_receipt"] and notified == [(t["id"], True)]
    # ikkinchi marta bosilsa xabar takrorlanmaydi
    await u.c.post(f"/api/wallet/topup/{t['id']}/paid", headers={"X-Dev-User": "90"})
    assert len(notified) == 1
    assert (await u.get("/wallet")).json()["pending_topup"]["status"] == "checking"
    lst = (await adm.get("/admin/topups/checking")).json()
    assert [x["id"] for x in lst] == [t["id"]]
    assert (await u.post(f"/admin/topups/{t['id']}/confirm")).status_code == 403
    assert (await adm.post(f"/admin/topups/{t['id']}/confirm")).json()["status"] == "paid"
    assert await get_balance(90) == t["pay_amount"]
    assert (await adm.post(f"/admin/topups/{t['id']}/confirm")).status_code == 409  # ikki marta tushmaydi
    assert await get_balance(90) == t["pay_amount"]


async def test_paid_reject_and_auto_match_while_checking(api, ctx, monkeypatch):
    async def fake_notify(t, user, image):
        pass

    monkeypatch.setattr(wallet_api, "_notify_review", fake_notify)
    await set_balance(91, 0)
    u, adm = api(91), api(1)
    t = (await u.post("/wallet/topup", {"amount": 20_000})).json()
    await u.post(f"/wallet/topup/{t['id']}/paid")
    r = (await adm.post(f"/admin/topups/{t['id']}/reject", {"reason": "Pul tushmagan"})).json()
    assert r["status"] == "rejected" and r["reject_reason"] == "Pul tushmagan"
    assert await get_balance(91) == 0
    assert any(uid == 91 and "tasdiqlanmadi" in text for uid, text, _ in ctx["sent"])
    assert (await u.post(f"/wallet/topup/{t['id']}/paid")).status_code == 409
    # tekshiruvdagi so'rov bank xabari kelganda avtomatik tasdiqlanadi
    t2 = (await u.post("/wallet/topup", {"amount": 30_000})).json()
    await u.post(f"/wallet/topup/{t2['id']}/paid")
    r = await adm.post("/admin/incoming", {"amount": t2["pay_amount"]})
    assert r.json()["status"] == "matched"
    assert await get_balance(91) == t2["pay_amount"]
    assert (await adm.post(f"/admin/topups/{t2['id']}/reject", {})).status_code == 409


async def test_timer_from_settings(api):
    from datetime import datetime

    await api(1).put("/admin/settings", {"key": "topup_timeout_minutes", "value": 15})
    t = (await api(92).post("/wallet/topup", {"amount": 10_000})).json()
    left = (datetime.fromisoformat(t["expires_at"]) - datetime.fromisoformat(t["created_at"])).total_seconds()
    assert 14 * 60 < left <= 15 * 60 + 5
    assert (await api(92).get("/wallet")).json()["limits"]["ttl_minutes"] == 15
