from datetime import datetime, timedelta, timezone

from app.db import SessionLocal
from app.models import PlusSub, User
from tests.conftest import get_balance, make_package, set_balance

ML = {"player_id": "123456789", "zone_id": "1234"}


async def test_summary_and_non_admin_forbidden(api):
    await set_balance(1, 0)
    await set_balance(5, 0)
    assert (await api(5).get("/admin/premium/summary")).status_code == 403
    r = await api(1).get("/admin/premium/summary")
    assert r.status_code == 200 and "kyc_pending" in r.json()


async def test_shop_toggle_and_edit(api, ctx):
    await set_balance(1, 0)
    await set_balance(10, 0)
    await api(10).post("/shop", {"slug": "kanal", "name": "Kanal", "tagline": ""})
    shops = (await api(1).get("/admin/premium/shops?q=kan")).json()
    sid = shops[0]["id"]
    assert shops[0]["owner_id"] == 10 and shops[0]["active"] is True
    assert (await api(1).put(f"/admin/premium/shops/{sid}", {"active": False, "name": "Kanal UZ"})).status_code == 200
    s = (await api(1).get("/admin/premium/shops")).json()[0]
    assert s["active"] is False and s["name"] == "Kanal UZ"
    assert any(uid == 10 and "to'xtatildi" in t for uid, t, _ in ctx["sent"])


async def test_plus_gift_days(api):
    await set_balance(1, 0)
    await set_balance(20, 0)
    r = await api(1).post("/admin/premium/plus/20/days", {"days": 30})
    assert r.status_code == 200
    async with SessionLocal() as s:
        sub = await s.get(PlusSub, 20)
        assert sub.until > datetime.now(timezone.utc) + timedelta(days=29)
    assert (await api(20).get("/plus")).json()["active"] is True
    assert len((await api(1).get("/admin/premium/plus")).json()) == 1


async def test_savings_and_split_cancel_refund(api):
    await set_balance(1, 0)
    await set_balance(30, 100_000)
    await set_balance(31, 100_000)
    pid = await make_package(40_000)
    sv = (await api(30).post("/savings", {"package_id": pid, **ML, "first": 10_000})).json()["items"][0]["id"]
    assert await get_balance(30) == 90_000
    assert (await api(1).post(f"/admin/premium/savings/{sv}/cancel")).status_code == 200
    assert await get_balance(30) == 100_000
    code = (await api(30).post("/split", {"mode": "split", "package_id": pid, **ML})).json()["code"]
    await api(31).post(f"/split/{code}/pay", {"amount": 15_000})
    assert (await api(1).get("/admin/premium/splits")).json()[0]["collected"] == 15_000
    assert (await api(1).post(f"/admin/premium/splits/{code}/cancel")).status_code == 200
    assert await get_balance(31) == 100_000


async def test_kyc_full_management(api, ctx):
    await set_balance(1, 0)
    await set_balance(40, 0)
    async with SessionLocal() as s, s.begin():
        (await s.get(User, 40)).kyc_status = "pending"
    r = (await api(1).get("/admin/premium/kyc?status=pending")).json()
    assert r["totals"]["pending"] == 1 and r["items"][0]["id"] == 40
    assert (await api(1).post("/admin/premium/kyc/40", {"action": "approve"})).json()["status"] == "verified"
    assert (await api(1).get("/admin/premium/kyc?status=verified&q=40")).json()["items"][0]["id"] == 40
    r = await api(1).post("/admin/premium/kyc/40", {"action": "reset", "note": "Hujjat muddati o'tgan"})
    assert r.json()["status"] == "none"
    assert any(uid == 40 and "bekor qilindi" in t for uid, t, _ in ctx["sent"])
    assert (await api(1).post("/admin/premium/kyc/40", {"action": "bogus"})).status_code == 422


async def test_texts_editable(api):
    await set_balance(1, 0)
    r = await api(1).put("/admin/settings", {"key": "text_home_title", "value": "Eng arzon almaz shu yerda"})
    assert r.status_code == 200, r.text
    assert (await api(1).get("/me")).json()["texts"]["home_title"] == "Eng arzon almaz shu yerda"
    assert (await api(1).put("/admin/settings", {"key": "text_home_title", "value": "x" * 200})).status_code == 400
    from app.services import launch

    await api(1).put("/admin/settings", {"key": "text_start", "value": "Salom, VAYNEXO!"})
    assert await launch.text("text_start") == "Salom, VAYNEXO!"
