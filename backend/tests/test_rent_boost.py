from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.db import SessionLocal
from app.models import Rental, Topup
from app.services import rental
from app.services.notify import Outbox
from tests.conftest import get_balance, set_balance

RL = {"game": "ML", "title": "Mythic · 120 skin", "rank": "Mythic", "server": "Asia", "skins": 120, "heroes": 85,
      "price_per_hour": 5_000, "description": "Ijaraga", "credentials": "login: owner@mail.com\nparol: Secret-1"}


async def _paid_topup(uid: int):
    async with SessionLocal() as s, s.begin():
        s.add(Topup(user_id=uid, requested_amount=10_000, pay_amount=10_001, status="paid",
                    expires_at=datetime.now(timezone.utc)))


async def _listing(api) -> int:
    await api(30).get("/me")
    r = await api(30).post("/rent/listings", RL)
    assert r.status_code == 200, r.text
    lid = r.json()["id"]
    assert (await api(31).get(f"/rent/listings/{lid}")).status_code == 404  # moderatsiyada
    await api(1).post(f"/admin/rent/listings/{lid}/moderate", {"approve": True})
    return lid


async def _expire(rid: int):
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Rental).where(Rental.id == rid).values(ends_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        await rental.tick(s, out)


async def test_rent_full_flow_percent_deposit(api):
    lid = await _listing(api)
    await set_balance(31, 200_000)
    renter, owner = api(31), api(30)
    cfg = (await renter.get("/rent/config")).json()
    assert [d["hours"] for d in cfg["durations"]] == [12, 24, 72, 168] and cfg["rent_deposit_type"] == "percent"

    assert (await renter.post(f"/rent/listings/{lid}/rent", {"hours": 12})).status_code == 403  # hali to'ldirmagan
    await _paid_topup(31)
    assert (await renter.post(f"/rent/listings/{lid}/rent", {"hours": 5})).status_code == 400  # noto'g'ri muddat
    r = (await renter.post(f"/rent/listings/{lid}/rent", {"hours": 12})).json()
    assert r["price"] == 60_000 and r["deposit"] == 60_000 and r["commission"] == 6_000  # 100% depozit, 10% komissiya
    assert await get_balance(31) == 200_000 - 120_000
    assert "Secret-1" in (await renter.get(f"/rentals/{r['id']}")).json()["credentials"]
    assert (await owner.get(f"/rentals/{r['id']}")).json()["credentials"] is None
    assert (await api(32).post(f"/rent/listings/{lid}/rent", {"hours": 12})).status_code in (403, 409)  # band
    assert (await owner.post(f"/rentals/{r['id']}/confirm")).status_code == 409  # muddat tugamagan

    await _expire(r["id"])
    v = (await renter.get(f"/rentals/{r['id']}")).json()
    assert v["status"] == "ended" and v["credentials"] is None  # muddat tugagach parol yopiladi
    assert (await owner.post(f"/rentals/{r['id']}/confirm")).json()["status"] == "completed"
    assert await get_balance(30) == 60_000 - 6_000
    assert await get_balance(31) == 200_000 - 60_000  # depozit qaytdi
    feed = (await api(33).get("/rent/listings?free=true")).json()
    assert feed["free"] == 1 and feed["items"][0]["busy_until"] is None


async def test_rent_fixed_deposit_and_owner_dispute(api):
    await api(1).put("/admin/settings", {"key": "rent_deposit_type", "value": "fixed"})
    await api(1).put("/admin/settings", {"key": "rent_deposit_fixed", "value": 50_000})
    assert (await api(1).put("/admin/settings", {"key": "rent_deposit_type", "value": "boshqa"})).status_code == 400
    lid = await _listing(api)
    await set_balance(31, 200_000)
    await _paid_topup(31)
    r = (await api(31).post(f"/rent/listings/{lid}/rent", {"hours": 24})).json()
    assert r["deposit"] == 50_000 and r["price"] == 120_000
    await _expire(r["id"])
    assert (await api(30).post(f"/rentals/{r['id']}/dispute", {"reason": "Parol almashtirilgan"})).json()["status"] == "disputed"
    res = await api(1).post(f"/admin/rentals/{r['id']}/resolve", {"decision": "owner", "note": "isbotlandi"})
    assert res.status_code == 200, res.text
    assert await get_balance(30) == 120_000 - 12_000 + 50_000  # depozit egasiga
    assert await get_balance(31) == 200_000 - 170_000


async def test_rent_auto_complete_after_review_window(api):
    lid = await _listing(api)
    await set_balance(31, 200_000)
    await _paid_topup(31)
    r = (await api(31).post(f"/rent/listings/{lid}/rent", {"hours": 12})).json()
    await _expire(r["id"])
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Rental).where(Rental.id == r["id"]).values(review_until=datetime.now(timezone.utc) - timedelta(minutes=1)))
    async with SessionLocal() as s, s.begin():
        await rental.tick(s, Outbox())
    assert (await api(31).get(f"/rentals/{r['id']}")).json()["status"] == "completed"
    assert await get_balance(31) == 200_000 - 60_000


async def test_boost_extras_percent_from_admin(api):
    base_body = {"current_rank": "Epic", "current_division": "V", "target_rank": "Mythic", "target_stars": 12}
    base = (await api(70).post("/boost/quote", base_body)).json()
    assert base["extras"] == [] and base["price"] == base["base"]
    q = (await api(70).post("/boost/quote", {**base_body, "express": True, "hero": "Fanny", "lane": "Jungle"})).json()
    b = base["base"]
    assert q["price"] == b + b * 30 // 100 + b * 15 // 100 + b * 10 // 100
    await api(1).put("/admin/settings", {"key": "boost_express_percent", "value": 50})
    q2 = (await api(70).post("/boost/quote", {**base_body, "express": True})).json()
    assert q2["price"] == b + b * 50 // 100
    assert (await api(70).post("/boost/quote", {**base_body, "lane": "Yo'q"})).status_code == 400


async def test_tg_prices_fixed_and_fragment_markup(api):
    from tests.conftest import get_balance, set_balance

    u, admin = api(77), api(1)
    await set_balance(77, 1_000_000)
    cat = (await u.get("/tg/catalog")).json()
    assert {p["months"]: p["price"] for p in cat["premium"]}[3] == 189_000 and cat["stars"]["rate"] == 220

    # Aniq narxni o'zgartirish
    await admin.put("/admin/settings", {"key": "premium_price_3", "value": 199_000})
    r = await u.post("/tg/orders", {"kind": "premium", "months": 3, "target_username": "@javohir_ml"})
    assert r.json()["price"] == 199_000

    # Fragment tannarxi + 15% ustama
    await admin.put("/admin/settings", {"key": "tg_price_mode", "value": "percent"})
    rows = {x["key"]: x for x in (await admin.get("/admin/settings")).json()}
    assert rows["premium_cost_3"]["show_if"] == {"key": "tg_price_mode", "value": "percent"}
    cat = (await u.get("/tg/catalog")).json()
    assert {p["months"]: p["price"] for p in cat["premium"]}[3] == 165_000 * 115 // 100  # 189 750
    assert cat["stars"]["rate"] == 218.5 and cat["stars"]["preset_prices"]["50"] == 10_925
    bal = await get_balance(77)
    r = await u.post("/tg/orders", {"kind": "stars", "stars": 101, "target_username": "@javohir_ml"})
    assert r.json()["price"] == 22_069  # 101 × 218.5 = 22 068.5 -> yuqoriga yaxlitlanadi
    assert await get_balance(77) == bal - 22_069

    # Gift narxi admin paneldan
    await admin.put("/admin/settings", {"key": "gift_price_bear", "value": 17_000})
    r = await u.post("/tg/orders", {"kind": "gift", "gift": "bear", "target_username": "@dilnoza_07"})
    assert r.json()["price"] == 17_000
    assert len((await u.get("/tg/orders")).json()) == 3
