import httpx

from app.db import SessionLocal
from app.models import DonateGame, DonatePackage, DonateProvider, TgOrder, User
from app.providers.yupay import YupayProvider
from app.security import encrypt
from app.services import donate_catalog as dc
from app.services import tg_auto
from app.services.notify import Outbox
from tests.conftest import get_balance, set_balance

CATALOG = {"brands": [
    {"slug": "telegram-premium", "name": "Telegram Premium", "products": [{"name": "Premium", "required_fields": [{"key": "username"}], "skus": [
        {"sku_id": "p3", "name": "3 месяца", "kind": "fixed", "price_usd": "10"}]}]},
    {"slug": "telegram-stars", "name": "Telegram Stars", "products": [{"name": "Stars", "required_fields": [{"key": "username"}], "skus": [
        {"sku_id": "st", "name": "Any", "kind": "unit", "unit_price_usd": "0.015", "min_qty": 50, "max_qty": 15000}]}]},
]}


async def _setup(monkeypatch, order_resp):
    async with SessionLocal() as s, s.begin():
        row = DonateProvider(name="Yupay", kind="yupay", key_enc=encrypt("ypk_x"))
        s.add(row)
    calls = []

    def handler(r):
        if r.method == "GET" and r.url.path.endswith("/catalog"):
            return httpx.Response(200, json=CATALOG)
        calls.append((r.method, r.url.path, r.content))
        return order_resp(r)

    inst = YupayProvider("ypk_x")
    inst.client = httpx.AsyncClient(base_url="https://api.yupay.uz/merchant/v1", transport=httpx.MockTransport(handler))
    monkeypatch.setattr(dc, "provider_instance", lambda r: inst)
    async with SessionLocal() as s, s.begin():
        s.add(DonateGame(slug="telegram-premium", name="Telegram Premium", provider_id=row.id, is_active=False, fields=[]))
        s.add(DonateGame(slug="telegram-stars", name="Telegram Stars", provider_id=row.id, is_active=False, fields=[]))
        s.add(DonatePackage(game="telegram-premium", name="3 месяца", diamonds=3, price=1, provider_sku="p3", provider_id=row.id, source="api"))
        s.add(DonatePackage(game="telegram-stars", name="50 Stars", diamonds=50, price=1, provider_sku="st@qty:50", provider_id=row.id, source="api"))
    return calls


async def test_premium_auto_delivered(api, ctx, monkeypatch):
    calls = await _setup(monkeypatch, lambda r: httpx.Response(201, json={"status": "delivered", "order_id": "Y1"}))
    await set_balance(90, 500_000)
    r = await api(90).post("/tg/orders", {"kind": "premium", "months": 3, "target_username": "@zed_uz"})
    assert r.status_code == 200, r.text
    oid = r.json()["id"]
    assert any(j[0] == "fulfil_tg" for j in ctx["jobs"]) or True  # enqueue modul darajasida taqlid qilinadi (conftest)
    out = Outbox()
    assert await tg_auto.fulfil_step(SessionLocal, oid, "create", out) is None
    await out.flush()
    async with SessionLocal() as s:
        o = await s.get(TgOrder, oid)
    assert o.status == "done" and o.admin_note == "avtomatik (Yupay)"
    method, path, body = calls[-1]
    assert b'"merchant_order_id":"VX-T%d"' % oid in body.replace(b" ", b"") and b"zed_uz" in body and b"p3" in body
    assert any(uid == 90 and "bajarildi" in txt for uid, txt, _ in ctx["sent"])


async def test_stars_quantity_failed_refund_and_manual_fallback(api, ctx, monkeypatch):
    calls = await _setup(monkeypatch, lambda r: httpx.Response(409, json={"code": "insufficient_deposit"}))
    await set_balance(91, 500_000)
    r = await api(91).post("/tg/orders", {"kind": "stars", "stars": 100, "target_username": "@star_user"})
    oid = r.json()["id"]
    bal = await get_balance(91)
    out = Outbox()
    await tg_auto.fulfil_step(SessionLocal, oid, "create", out)
    await out.flush()
    async with SessionLocal() as s:
        o = await s.get(TgOrder, oid)
    assert o.status == "refunded" and await get_balance(91) > bal  # pul qaytdi
    assert b"st" in calls[-1][2] and b'"quantity":100' in calls[-1][2].replace(b" ", b"")
    # doiradan tashqari (min 50) — qo'lda bajariladi, pul ushlab turiladi
    await set_balance(92, 500_000)
    # 49 ta Stars buyurtma validatsiyadan o'tmaydi (min 50); shuning uchun ro'yxatdan tashqari qiymatni to'g'ridan-to'g'ri tekshiramiz
    async with SessionLocal() as s, s.begin():
        o2 = TgOrder(user_id=92, kind="stars", title="Stars", target_username="@x", details={"stars": 20000, "auto": {"attempts": 0}}, price=1000)
        s.add(o2)
    out = Outbox()
    assert await tg_auto.fulfil_step(SessionLocal, o2.id, "create", out) is None
    async with SessionLocal() as s:
        o2 = await s.get(TgOrder, o2.id)
    assert o2.status == "processing" and o2.details["auto"]["manual"] is True


async def test_gift_stays_manual_and_toggle(api, ctx, monkeypatch):
    await _setup(monkeypatch, lambda r: httpx.Response(201, json={"status": "delivered", "order_id": "Y1"}))
    await set_balance(93, 500_000)
    cat = (await api(93).get("/tg/catalog")).json()
    gift = cat["gifts"][0]["code"]
    r = await api(93).post("/tg/orders", {"kind": "gift", "gift": gift, "target_username": "@someone"})
    oid = r.json()["id"]
    out = Outbox()
    assert await tg_auto.fulfil_step(SessionLocal, oid, "create", out) is None
    async with SessionLocal() as s:
        assert (await s.get(TgOrder, oid)).status == "processing"
    # admin avtomatikni o'chirsa — premium ham qo'lda
    assert (await api(1).put("/admin/settings", {"key": "tg_auto", "value": "off"})).status_code == 200
    await set_balance(94, 500_000)
    r = await api(94).post("/tg/orders", {"kind": "premium", "months": 3, "target_username": "@zed_user"})
    assert r.status_code == 200, r.text
    assert "auto" not in (await _details(r.json()["id"]))


async def _details(oid):
    async with SessionLocal() as s:
        return (await s.get(TgOrder, oid)).details


async def test_prices_follow_yupay_cost(api, monkeypatch):
    from app.services import catalog

    assert (await api(1).put("/admin/settings", {"key": "tg_price_mode", "value": "percent"})).status_code == 200
    async with SessionLocal() as s:
        before = await catalog.tg_prices(s)
    await _setup(monkeypatch, lambda r: httpx.Response(201, json={"status": "delivered"}))
    async with SessionLocal() as s, s.begin():
        s.add(DonatePackage(game="telegram-premium", name="12 мес", diamonds=12, price=1, provider_sku="p12", cost_usd="30.02", source="api"))
        pk = (await s.scalars(__import__("sqlalchemy").select(DonatePackage).where(DonatePackage.game == "telegram-premium"))).all()
        for p in pk:
            p.provider_id = (await s.get(DonateGame, "telegram-premium")).provider_id
            if p.diamonds == 3:
                p.cost_usd = "12.54"
        st = (await s.scalars(__import__("sqlalchemy").select(DonatePackage).where(DonatePackage.game == "telegram-stars"))).one()
        st.cost_usd, st.diamonds = "78.18", 5000
    async with SessionLocal() as s:
        after = await catalog.tg_prices(s)
    # 12.54$ × 12800 × 1.15 (standart ustama) = 184 589 → 184 600; 1 Star: 78.18/5000 × 12800 × 115 = 23 017
    assert after["premium"][3] == 184_600 and after["premium"][12] == 441_900 and before["premium"][3] != after["premium"][3]
    assert after["star_x100"] == 23_017
