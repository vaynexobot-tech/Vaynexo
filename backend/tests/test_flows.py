import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db import SessionLocal
from app.errors import InsufficientFunds
from app.models import Deal, DonateOrder, LedgerEntry
from app.providers import ProviderResult, set_provider
from app.providers.mock import MockProvider
from app.services import donate, market, wallet
from app.services.notify import Outbox
from tests.conftest import get_balance, make_package, set_balance


async def run_donate(order_id: int) -> str:
    """Workerni simulyatsiya qiladi: qadamlarni yakunlanguncha bajaradi."""
    mode = "create"
    for _ in range(60):
        out = Outbox()
        nxt = await donate.fulfil_step(SessionLocal, order_id, mode, out)
        await out.flush()
        if not nxt:
            break
        mode = nxt[0]
    async with SessionLocal() as s:
        return (await s.get(DonateOrder, order_id)).status


# ------------------------------------------------------------------ hamyon
async def test_concurrent_debits_never_overdraw():
    await set_balance(20, 100_000)

    async def spend(i):
        async with SessionLocal() as s:
            try:
                async with s.begin():
                    await wallet.debit(s, 20, 30_000, "test", f"t:{i}")
                return True
            except InsufficientFunds:
                return False

    results = await asyncio.gather(*(spend(i) for i in range(10)))
    assert sum(results) == 3
    assert await get_balance(20) == 10_000
    async with SessionLocal() as s:
        entries = list(await s.scalars(select(LedgerEntry).where(LedgerEntry.user_id == 20)))
    assert len(entries) == 3


# ------------------------------------------------------------------ donat
async def test_donate_success(api, ctx):
    set_provider(MockProvider())
    pkg = await make_package(37_000)
    await set_balance(30, 50_000)
    r = await api(30).post("/donate/orders", {"package_id": pkg, "player_id": "84512937", "zone_id": "2104"})
    assert r.status_code == 200, r.text
    order = r.json()
    assert await get_balance(30) == 13_000
    assert ("fulfil_donate", order["id"], "create") in ctx["jobs"]
    assert await run_donate(order["id"]) == "done"
    assert await get_balance(30) == 13_000
    assert any("yetkazildi" in m[1] for m in ctx["sent"] if m[0] == 30)


async def test_donate_insufficient_funds(api):
    pkg = await make_package(37_000)
    await set_balance(31, 10_000)
    r = await api(31).post("/donate/orders", {"package_id": pkg, "player_id": "84512937", "zone_id": "2104"})
    assert r.status_code == 402
    assert await get_balance(31) == 10_000


async def test_donate_provider_error_refunds(api, ctx):
    set_provider(MockProvider())
    pkg = await make_package(37_000)
    await set_balance(32, 37_000)
    order = (await api(32).post("/donate/orders", {"package_id": pkg, "player_id": "01234567", "zone_id": "2104"})).json()
    assert await get_balance(32) == 0
    assert await run_donate(order["id"]) == "refunded"
    assert await get_balance(32) == 37_000
    assert any("qaytarildi" in m[1] for m in ctx["sent"] if m[0] == 32)
    assert any("Donat xatosi" in m[1] for m in ctx["sent"] if m[0] == 1)  # admin
    # Qayta ishga tushirilsa ham ikkinchi marta qaytarilmaydi
    assert await run_donate(order["id"]) == "refunded"
    assert await get_balance(32) == 37_000


async def test_donate_unknown_goes_to_review_then_admin_refund(api, ctx):
    class Silent(MockProvider):
        async def create(self, *a):
            return ProviderResult("unknown", message="timeout")

        async def status(self, ref):
            return ProviderResult("unknown", message="timeout")

    set_provider(Silent())
    pkg = await make_package(20_000)
    await set_balance(33, 20_000)
    order = (await api(33).post("/donate/orders", {"package_id": pkg, "player_id": "84512937", "zone_id": "1"})).json()
    assert await run_donate(order["id"]) == "review"
    assert await get_balance(33) == 0  # noma'lum holatda pul avtomatik qaytarilmaydi
    r = await api(1).post(f"/admin/donate/{order['id']}", {"action": "refund"})
    assert r.status_code == 200, r.text
    assert await get_balance(33) == 20_000
    set_provider(MockProvider())


async def test_donate_retry_detects_earlier_success(api):
    """Birinchi so'rov javobsiz qoldi, lekin provayderda bajarilgan — ikkinchi marta yuborilmaydi."""
    calls = {"create": 0}

    class Flaky(MockProvider):
        async def create(self, *a):
            calls["create"] += 1
            return ProviderResult("unknown", message="timeout")

        async def status(self, ref):
            return ProviderResult("success", ref="P-1")

    set_provider(Flaky())
    pkg = await make_package(10_000)
    await set_balance(34, 10_000)
    order = (await api(34).post("/donate/orders", {"package_id": pkg, "player_id": "84512937", "zone_id": "1"})).json()
    assert await run_donate(order["id"]) == "done"
    assert calls["create"] == 1
    set_provider(MockProvider())


# ------------------------------------------------------------------ akkaunt savdo
LISTING = {"game": "ML", "title": "Mythic akkaunt · 74 skin", "rank": "Mythic", "server": "Asia",
           "collection_level": "Mega Collector", "skins": 74, "heroes": 80, "price": 420_000, "description": "Toza"}


async def _active_listing(api, seller=40) -> int:
    r = await api(seller).post("/listings", LISTING)
    assert r.status_code == 200, r.text
    lid = r.json()["id"]
    assert (await api(41).get(f"/listings/{lid}")).status_code == 404  # moderatsiyadagi e'lon ko'rinmaydi
    r = await api(1).post(f"/admin/listings/{lid}/moderate", {"approve": True})
    assert r.status_code == 200, r.text
    return lid


async def test_full_deal_flow(api, ctx):
    lid = await _active_listing(api)
    await set_balance(41, 500_000)
    buyer, seller = api(41), api(40)

    feed = (await buyer.get("/listings?game=ML&sort=cheap")).json()
    assert [x["id"] for x in feed["items"]] == [lid]

    chat = (await buyer.post(f"/listings/{lid}/chat")).json()
    await buyer.post(f"/chats/{chat['id']}/messages", {"text": "Salom, amalda?"})
    msgs = (await seller.get(f"/chats/{chat['id']}")).json()["messages"]
    assert msgs[-1]["text"] == "Salom, amalda?"
    assert (await api(99).get(f"/chats/{chat['id']}")).status_code == 404

    assert (await seller.post(f"/listings/{lid}/buy")).status_code == 400  # o'zinikini sotib ololmaydi
    deal = (await buyer.post(f"/listings/{lid}/buy")).json()
    assert deal["status"] == "paid" and await get_balance(41) == 80_000
    assert (await api(42).post(f"/listings/{lid}/buy")).status_code == 409  # band

    assert (await buyer.post(f"/deals/{deal['id']}/deliver", {"credentials": "x@gmail.com / 123"})).status_code == 403
    r = await seller.post(f"/deals/{deal['id']}/deliver", {"credentials": "login: x@gmail.com\nparol: secret123"})
    assert r.status_code == 200
    assert "secret123" in (await buyer.get(f"/deals/{deal['id']}")).json()["credentials"]
    assert (await seller.get(f"/deals/{deal['id']}")).json()["credentials"] is None
    async with SessionLocal() as s:
        assert "secret123" not in (await s.get(Deal, deal["id"])).credentials_enc  # bazada shifrlangan

    await buyer.post(f"/deals/{deal['id']}/confirm")
    assert await get_balance(40) == 420_000 - 21_000  # 5% komissiya
    assert (await buyer.post(f"/deals/{deal['id']}/confirm")).status_code == 409
    assert await get_balance(40) == 399_000

    assert (await buyer.post(f"/deals/{deal['id']}/review", {"score": 5, "tags": ["Tez javob"]})).status_code == 200
    assert (await buyer.post(f"/deals/{deal['id']}/review", {"score": 5})).status_code == 409
    me = (await seller.get("/me")).json()
    assert me["rating"] == 5.0 and me["sales"] == 1


async def test_parallel_buy_only_one_wins(api):
    lid = await _active_listing(api)
    for uid in (50, 51, 52, 53):
        await set_balance(uid, 1_000_000)
    rs = await asyncio.gather(*(api(uid).post(f"/listings/{lid}/buy") for uid in (50, 51, 52, 53)))
    assert sorted(r.status_code for r in rs) == [200, 409, 409, 409]
    total = sum([await get_balance(uid) for uid in (50, 51, 52, 53)])
    assert total == 4_000_000 - 420_000


async def test_dispute_refund_and_auto_release(api, ctx):
    lid = await _active_listing(api)
    await set_balance(41, 420_000)
    buyer, seller = api(41), api(40)
    deal = (await buyer.post(f"/listings/{lid}/buy")).json()
    await seller.post(f"/deals/{deal['id']}/deliver", {"credentials": "login/parol"})
    r = await buyer.post(f"/deals/{deal['id']}/dispute", {"reason": "Parol to'g'ri kelmadi"})
    assert r.json()["status"] == "disputed"
    r = await api(1).post(f"/admin/deals/{deal['id']}/resolve", {"winner": "buyer", "note": "parol noto'g'ri"})
    assert r.status_code == 200, r.text
    assert await get_balance(41) == 420_000 and await get_balance(40) == 0

    # Avto-tasdiq: muddat o'tgach pul sotuvchiga o'tadi.
    lid2 = await _active_listing(api, seller=43)
    deal2 = (await buyer.post(f"/listings/{lid2}/buy")).json()
    await api(43).post(f"/deals/{deal2['id']}/deliver", {"credentials": "login/parol"})
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Deal).where(Deal.id == deal2["id"]).values(auto_release_at=datetime.now(timezone.utc) - timedelta(minutes=1)))
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        assert await market.auto_release(s, out) == 1
    assert await get_balance(43) == 399_000


async def test_seller_cancel_refunds_and_relists(api):
    lid = await _active_listing(api)
    await set_balance(41, 420_000)
    deal = (await api(41).post(f"/listings/{lid}/buy")).json()
    assert (await api(41).post(f"/deals/{deal['id']}/cancel")).status_code == 409  # xaridor 12 soat kutadi
    assert (await api(40).post(f"/deals/{deal['id']}/cancel")).status_code == 200
    assert await get_balance(41) == 420_000


# ------------------------------------------------------------------ TG, boost, arena
async def test_tg_order_and_refund(api, ctx):
    await set_balance(60, 200_000)
    u = api(60)
    r = await u.post("/tg/orders", {"kind": "premium", "months": 3, "target_username": "@javohir_ml"})
    assert r.status_code == 200, r.text
    assert await get_balance(60) == 11_000
    r = await u.post("/tg/orders", {"kind": "stars", "stars": 10, "target_username": "javohir_ml"})
    assert r.status_code == 400  # minimal 50
    oid = (await api(1).get("/admin/tg")).json()[0]["id"]
    await api(1).post(f"/admin/tg/{oid}", {"action": "refund", "note": "username topilmadi"})
    assert await get_balance(60) == 200_000


async def test_boost_flow(api, ctx):
    from app.models import User
    from app.services import services as svc

    await set_balance(70, 500_000)
    await set_balance(71, 0)  # booster
    u = api(70)
    q = (await u.post("/boost/quote", {"current_rank": "Epic", "current_division": "V", "target_rank": "Mythic", "target_stars": 12})).json()
    assert q["stars"] == 62 and q["price"] == 25 * 4_000 + 25 * 5_000 + 12 * 7_000
    r = await u.post("/boost/orders", {"current_rank": "Epic", "target_rank": "Mythic", "target_stars": 12,
                                       "login_method": "moonton", "credentials": "id 123 / parol"})
    assert r.status_code == 200, r.text
    oid = r.json()["id"]
    assert ("post_boost", oid) in ctx["jobs"]
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        booster = await s.get(User, 71)
        await svc.boost_accept(s, oid, booster, out)
    for step in ("start", "finish"):
        async with SessionLocal() as s, s.begin():
            await svc.boost_progress(s, oid, 71, step, out)
    r = await u.post(f"/boost/orders/{oid}/confirm")
    assert r.json()["status"] == "done"
    assert await get_balance(71) == q["price"] * 70 // 100


async def test_tournament_join(api):
    await set_balance(80, 15_000)
    r = await api(1).post("/admin/tournaments", {"title": "Noyabr kubogi", "game": "ML", "prize_fund": 1_000_000,
                                                 "entry_fee": 10_000, "max_players": 2,
                                                 "starts_at": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()})
    tid = r.json()["id"]
    body = {"nick": "Shoxrux", "game_id": "84512937", "server": "2104"}
    assert (await api(80).post(f"/tournaments/{tid}/join", body)).json()["joined"] is True
    assert await get_balance(80) == 5_000
    assert (await api(80).post(f"/tournaments/{tid}/join", body)).status_code == 409
    assert (await api(81).post(f"/tournaments/{tid}/join", body)).status_code == 402  # pul yo'q


async def test_history_and_top(api):
    set_provider(MockProvider())
    pkg = await make_package(37_000)
    await set_balance(90, 100_000)
    order = (await api(90).post("/donate/orders", {"package_id": pkg, "player_id": "84512937", "zone_id": "2104"})).json()
    await run_donate(order["id"])
    h = (await api(90).get("/history")).json()
    assert h["items"][0]["type"] == "donate" and h["spent"] == 37_000
    top = (await api(90).get("/top?period=week")).json()
    assert top["me"]["place"] == 1 and top["me"]["total"] == 37_000


async def test_admin_forbidden_and_ban(api):
    assert (await api(5).get("/admin/stats")).status_code == 403
    assert (await api(1).get("/admin/stats")).status_code == 200
    await api(5).get("/me")
    await api(1).post("/admin/users/5/ban", {"banned": True})
    assert (await api(5).get("/me")).status_code == 403
    r = await api(1).post("/admin/users/6/balance", {"amount": 5_000, "note": "bonus", "request_id": "req-12345"})
    assert r.status_code == 404  # hali yo'q foydalanuvchi
    await api(6).get("/me")
    for _ in range(2):  # ikki marta bosilsa ham bir marta
        await api(1).post("/admin/users/6/balance", {"amount": 5_000, "note": "bonus", "request_id": "req-12345"})
    assert await get_balance(6) == 5_000


async def test_admin_changes_referral_bonus(api, client):
    from tests.test_security_p2p import make_init_data

    admin = api(1)
    rows = (await admin.get("/admin/settings")).json()
    assert {r["key"]: r["value"] for r in rows}["referral_bonus"] == 2000  # conftest: REFERRAL_BONUS=2000
    assert (await api(5).put("/admin/settings", {"key": "referral_bonus", "value": 1})).status_code == 403
    assert (await admin.put("/admin/settings", {"key": "referral_bonus", "value": -5})).status_code == 400
    r = await admin.put("/admin/settings", {"key": "referral_bonus", "value": 1234})
    assert {x["key"]: x["value"] for x in r.json()}["referral_bonus"] == 1234

    await set_balance(700, 0)
    h = {"Authorization": "tma " + make_init_data({"id": 701, "first_name": "D"}, start_param="ref_700")}
    t = (await client.post("/api/wallet/topup", json={"amount": 15_000}, headers=h)).json()
    await client.post("/api/p2p/incoming", json={"amount": t["pay_amount"]}, headers={"X-P2P-Secret": "test-secret"})
    assert await get_balance(700) == 1234
    me = (await api(700).get("/me")).json()
    assert me["referral_bonus"] == 1234 and me["ref_invited"] == 1 and me["ref_paid"] == 1 and me["ref_earned"] == 1234


async def test_top_counts_all_spending_minus_refunds(api):
    set_provider(MockProvider())
    pkg = await make_package(37_000)
    await set_balance(95, 500_000)
    await set_balance(96, 500_000)
    u = api(95)
    o = (await u.post("/donate/orders", {"package_id": pkg, "player_id": "84512937", "zone_id": "1"})).json()
    await run_donate(o["id"])
    await u.post("/tg/orders", {"kind": "premium", "months": 3, "target_username": "@javohir_ml"})  # 189 000
    o2 = (await api(96).post("/donate/orders", {"package_id": pkg, "player_id": "01234567", "zone_id": "1"})).json()
    await run_donate(o2["id"])  # rad etildi -> qaytarildi, reytingga kirmaydi
    top = (await u.get("/top?period=week")).json()
    assert [(r["user_id"], r["total"]) for r in top["items"]] == [(95, 37_000 + 189_000)]


async def test_market_grid_favorites_vip(api):
    lid = await _active_listing(api)  # sotuvchi 40, 420 000
    lid2 = (await api(40).post("/listings", {**LISTING, "title": "Legend · 41 skin", "price": 300_000})).json()["id"]
    await api(1).post(f"/admin/listings/{lid2}/moderate", {"approve": True})
    buyer, seller = api(41), api(40)

    feed = (await buyer.get("/listings")).json()
    assert feed["total"] == 2 and [x["id"] for x in feed["items"]] == [lid2, lid]  # eng yangisi birinchi

    # Sevimlilar: toggle
    assert (await buyer.post(f"/listings/{lid}/favorite")).json()["is_fav"] is True
    favs = (await buyer.get("/listings?favorites=true")).json()
    assert [x["id"] for x in favs["items"]] == [lid] and favs["items"][0]["is_fav"] is True
    assert (await buyer.post(f"/listings/{lid}/favorite")).json()["is_fav"] is False
    assert (await buyer.get("/listings?favorites=true")).json()["total"] == 0

    # VIP: pul yechiladi va e'lon tepaga chiqadi
    assert (await seller.get("/vip/price")).json()["price_per_day"] == 5_000
    assert (await seller.post(f"/listings/{lid}/vip", {"days": 3})).status_code == 402  # balans 0
    await set_balance(40, 20_000)
    r = await seller.post(f"/listings/{lid}/vip", {"days": 3})
    assert r.status_code == 200 and r.json()["vip"] is True
    assert await get_balance(40) == 5_000
    assert (await buyer.post(f"/listings/{lid}/vip", {"days": 1})).status_code == 404  # boshqaning e'loni
    feed = (await buyer.get("/listings")).json()
    assert [x["id"] for x in feed["items"]] == [lid, lid2] and feed["items"][0]["vip"] is True
    d = (await buyer.get(f"/listings/{lid}")).json()
    assert d["seller_verified"] is False and d["is_fav"] is False
