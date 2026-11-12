from app.services import reports
from tests.conftest import get_balance


async def test_audit_log_and_user_card(api):
    await api(80).get("/me")
    r = await api(1).post("/admin/users/80/balance", {"amount": 5000, "note": "sovg'a", "request_id": "req-0001"})
    assert r.status_code == 200
    # muvaffaqiyatsiz amal jurnalga yozilmaydi
    assert (await api(1).post("/admin/users/80/balance", {"amount": 0, "note": "xato", "request_id": "req-0002"})).status_code == 400
    logs = (await api(1).get("/admin/audit")).json()
    assert logs[0]["action"] == "Balansni o'zgartirish" and logs[0]["target_user"] == 80 and logs[0]["amount"] == 5000
    assert len([x for x in logs if x["target_user"] == 80]) == 1
    card = (await api(1).get("/admin/users/80/card")).json()
    assert card["user"]["balance"] == 5000 and card["ledger"][0]["kind"] == "admin_adjust"
    assert card["admin_log"][0]["action"] == "Balansni o'zgartirish"
    assert (await api(80).get("/admin/audit")).status_code == 403


async def test_secrets_not_logged(api):
    await api(1).post("/admin/tg-bank/api", {"api_id": "12345", "api_hash": "b" * 32})
    logs = (await api(1).get("/admin/audit")).json()
    assert "b" * 32 not in logs[0]["summary"] and "•••" in logs[0]["summary"]


async def test_promo_codes(api, ctx):
    r = await api(1).post("/admin/promo", {"code": "vaynexo 2026!", "amount": 3000, "max_uses": 2, "need_topup": False})
    assert r.status_code == 200 and r.json()["code"] == "VAYNEXO2026"
    assert (await api(1).post("/admin/promo", {"code": "VAYNEXO2026", "amount": 1})).status_code == 409
    assert (await api(81).post("/wallet/promo", {"code": "vaynexo2026"})).json()["amount"] == 3000
    assert await get_balance(81) == 3000
    assert (await api(81).post("/wallet/promo", {"code": "VAYNEXO2026"})).status_code == 400  # takror
    assert (await api(82).post("/wallet/promo", {"code": "VAYNEXO2026"})).status_code == 200
    assert (await api(83).post("/wallet/promo", {"code": "VAYNEXO2026"})).status_code == 400  # limit
    assert (await api(83).post("/wallet/promo", {"code": "YOQ"})).status_code == 404
    # faqat to'ldirganlar uchun
    await api(1).post("/admin/promo", {"code": "TOPUP", "amount": 1000})
    assert (await api(84).post("/wallet/promo", {"code": "TOPUP"})).json()["error"] == "promo_need_topup"
    hist = (await api(81).get("/history")).json()["items"]
    assert hist[0]["title"] == "Promo-kod bonusi"
    # yechib bo'lmaydi
    w = (await api(81).get("/wallet")).json()
    assert w["withdraw"]["available"] == 0


async def test_analytics_and_daily_report(api, ctx):
    await api(85).get("/me")
    await api(1).post("/admin/incoming", {"amount": 40_000, "user_id": 85})
    a = (await api(1).get("/admin/analytics?days=7")).json()
    assert len(a["days"]) == 7 and a["total"]["topup"] >= 40_000
    r = (await api(1).post("/admin/report/send")).json()
    assert "Kunlik hisobot" in r["text"]
    assert any("Kunlik hisobot" in m[1] for m in ctx["sent"])
    from app.db import SessionLocal

    async with SessionLocal() as s:
        assert "To'ldirildi" in await reports.daily_text(s)


async def test_broadcast(api, ctx):
    import asyncio

    for uid in (90, 91, 92):
        await api(uid).get("/me")
    st = (await api(1).get("/admin/broadcast")).json()
    assert {a["v"] for a in st["audiences"]} >= {"all", "active7", "sellers"}
    r = await api(1).post("/admin/broadcast", {"text": "Sinov", "test": True})
    assert r.json()["test"] and ctx["sent"][-1][0] == 1
    r = await api(1).post("/admin/broadcast", {"text": "🎉 Aksiya!", "audience": "active7"})
    assert r.status_code == 200 and r.json()["total"] >= 3
    for _ in range(100):
        if not (await api(1).get("/admin/broadcast")).json()["running"]:
            break
        await asyncio.sleep(0.05)
    got = {m[0] for m in ctx["sent"] if m[1] == "🎉 Aksiya!"}
    assert {90, 91, 92} <= got


async def test_tg_login_code_masked(api):
    from app.services import audit

    s, _ = audit._clean(b'{"code": "12345"}', "/api/admin/tg-bank/login")
    assert "12345" not in s
    s, _ = audit._clean(b'{"code": "START", "need_topup": true}', "/api/admin/promo")
    assert "START" in s and "need_topup: ha" in s
