import json

import httpx
import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import DonateGame, DonatePackage, DonateProvider
from app.providers.yupay import YupayProvider
from app.services import donate_catalog as dc

CATALOG = {"brands": [
    {"slug": "mobile-legends", "name": "Mobile Legends", "logo_url": "https://cdn/ml.png", "category_name": "Top-ups", "products": [{
        "name": "Diamonds", "required_fields": [{"key": "player_id", "label": "User ID", "pattern": "^\\d{5,20}$"},
                                                {"key": "server_id", "label": "Zone ID", "pattern": "^\\d{1,10}$"}],
        "skus": [{"sku_id": "sku-86", "name": "86 Diamonds", "kind": "fixed", "price_usd": "1.20", "stock": None},
                 {"sku_id": "sku-172", "name": "172 Diamonds", "kind": "fixed", "price_usd": "2.40", "stock": None},
                 {"sku_id": "sku-out", "name": "Yo'q", "kind": "fixed", "price_usd": "9.00", "stock": 0},
                 {"sku_id": "sku-unit", "name": "Unit", "kind": "unit", "price_usd": "0.01"}]}]},
    {"slug": "mobile-legends-ru", "name": "Mobile Legends RU", "products": [{"name": "x", "skus": [{"sku_id": "r1", "name": "RU 86", "kind": "fixed", "price_usd": "1"}]}]},
    {"slug": "pubg-mobile", "name": "PUBG Mobile", "logo_url": "https://cdn/pubg.png", "products": [{
        "name": "UC", "required_fields": [{"key": "player_id", "label": "Character ID", "pattern": ""}],
        "skus": [{"sku_id": "u60", "name": "60 UC", "kind": "fixed", "price_usd": "0.95"}]}]},
    {"slug": "steam", "name": "Steam", "products": [{"name": "Wallet", "skus": [{"sku_id": "s1", "name": "$5", "kind": "fixed", "price_usd": "5.2"}]}]},
]}


def test_price_formula():
    assert dc.price_uzs("2.40", 12_800, 10) == 33_800  # 2.4*12800*1.1 = 33792 → 33800
    assert dc.price_uzs("1.00", 12_800, 0) == 12_800
    assert dc.price_uzs("0.001", 12_800, 10) == 100  # kamida 100 ga yuqoriga
    assert dc.price_uzs("abc", 12_800, 10) == 0


def test_parse_and_clean_names():
    assert dc.parse_amount("172 (156+16) Diamonds") == (156, 16)
    assert dc.parse_amount("60 UC") == (60, 0) and dc.parse_amount("1,000 Robux") == (1000, 0)
    assert dc.parse_amount("Weekly Pass") == (0, 0)
    assert dc.clean_name("Mobile Legends 86 Diamonds", "Mobile Legends") == "86 Diamonds"
    assert dc.clean_name("Weekly Pass", "Mobile Legends") == "Weekly Pass"


def test_game_slug_mapping():
    assert dc.game_slug("mobile-legends") == "ML" and dc.game_slug("mobile-legends-ru") == "mobile-legends-ru"
    assert dc.game_slug("magic-chess-gogo") == "MC" and dc.game_slug("magic-chess-gogo-ru") == "magic-chess-gogo-ru"
    assert dc.game_slug("pubg-mobile") == "pubg-mobile"


async def _provider(monkeypatch, catalog=CATALOG) -> DonateProvider:
    from app.security import encrypt

    async with SessionLocal() as s, s.begin():
        row = DonateProvider(name="Yupay", kind="yupay", key_enc=encrypt("ypk_x"))
        s.add(row)
    inst = YupayProvider("ypk_x")
    inst.client = httpx.AsyncClient(base_url="https://api.yupay.uz/merchant/v1", transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=catalog)))
    monkeypatch.setitem(dc._instances, row.id, (None, inst))
    monkeypatch.setattr(dc, "provider_instance", lambda r: inst)
    return row


async def test_sync_creates_games_and_packages(api, monkeypatch):
    # admin oldindan qo'ygan «PUBG» joy-egasi (slug boshqacha) — sinxronlashda bog'lanadi
    async with SessionLocal() as s, s.begin():
        s.add(DonateGame(slug="pubg", name="PUBG Mobile", featured_slot=2, sort=1, fields=[]))
        s.add(DonatePackage(game="ML", name="172 almaz", diamonds=172, price=37_000, provider_sku="ML_172"))
        s.add(DonatePackage(game="ML", name="Haftalik pass", price=20_000, provider_sku="ML_WP"))
    row = await _provider(monkeypatch)
    async with SessionLocal() as s, s.begin():
        stats = await dc.sync_provider(s, await s.get(DonateProvider, row.id))
    assert stats["packages"] == 6 and "Mobile Legends RU" in stats["new_games"]
    async with SessionLocal() as s:
        games = {g.slug: g for g in await s.scalars(select(DonateGame))}
        assert "pubg" not in games and games["pubg-mobile"].featured_slot == 2 and games["pubg-mobile"].provider_id == row.id
        assert games["ML"].logo_url == "https://cdn/ml.png" and games["ML"].brand_slug == "mobile-legends"
        assert [f["key"] for f in games["ML"].fields] == ["player_id", "server_id"]
        assert games["mobile-legends-ru"].is_active is False  # yangi topilgan o'yin yashirin (admin yoqadi)
        pk = {p.provider_sku: p for p in await s.scalars(select(DonatePackage).where(DonatePackage.source == "api"))}
        assert set(pk) == {"sku-86", "sku-172", "sku-out", "u60", "s1", "r1"}  # unit SKU kirmaydi
        assert pk["sku-172"].price == 33_800 and pk["sku-172"].cost_usd == "2.40"
        assert pk["sku-out"].is_active is False and pk["sku-86"].is_active is True
        manual = {p.name: p for p in await s.scalars(select(DonatePackage).where(DonatePackage.source == "manual"))}
        assert manual["172 almaz"].is_active is False  # API'da xuddi shu miqdor bor — qo'lda nusxa o'chirildi
        assert manual["Haftalik pass"].is_active is True  # qo'shimcha qo'lda paket qoladi
        assert pk["sku-172"].diamonds == 172 and pk["sku-86"].sort < pk["sku-172"].sort  # narx bo'yicha tartib


async def test_sync_reprice_and_admin_hide(api, monkeypatch):
    row = await _provider(monkeypatch)
    async with SessionLocal() as s, s.begin():
        await dc.sync_provider(s, await s.get(DonateProvider, row.id))
    # admin paketni yashiradi — sinxronlash qayta yoqmaydi
    async with SessionLocal() as s:
        pid = (await s.scalar(select(DonatePackage.id).where(DonatePackage.provider_sku == "sku-86")))
    r = await api(1).put(f"/admin/packages/{pid}", {"game": "ML", "name": "86 Diamonds", "price": 17_000, "provider_sku": "sku-86", "is_active": False})
    assert r.status_code == 200
    async with SessionLocal() as s, s.begin():
        await dc.sync_provider(s, await s.get(DonateProvider, row.id))
        p = await s.get(DonatePackage, pid)
        assert p.is_active is False and p.price == 16_900  # narx tannarxdan qayta hisoblangan (1.2*12800*1.1)
    # kurs o'zgardi → reprice
    assert (await api(1).put("/admin/settings", {"key": "donate_usd_rate", "value": 13_000})).status_code == 200
    assert (await api(1).post("/admin/donate/reprice")).json()["changed"] >= 1


async def test_public_games_and_packages(api, monkeypatch):
    row = await _provider(monkeypatch)
    async with SessionLocal() as s, s.begin():
        await dc.sync_provider(s, await s.get(DonateProvider, row.id))
    # admin: PUBG va Steam asosiy kartalarga, MLBB 1-o'rinda
    assert (await api(1).put("/admin/donate/games/pubg-mobile", {"is_active": True, "featured_slot": 2})).status_code == 200
    assert (await api(1).put("/admin/donate/games/steam", {"is_active": True, "featured_slot": 3})).status_code == 200
    assert (await api(1).put("/admin/donate/games/mobile-legends-ru", {"is_active": True, "popular": True})).status_code == 200
    g = (await api(5).get("/donate/games")).json()
    assert [x["slug"] for x in g["featured"]] == ["ML", "pubg-mobile", "steam"] and all(x["available"] for x in g["featured"])
    assert [x["slug"] for x in g["popular"]] == ["mobile-legends-ru"]
    assert "MC" not in [x["slug"] for x in g["all"]]  # Magic Chess yashirin
    pk = (await api(5).get("/donate/packages?game=pubg-mobile")).json()
    assert [p["name"] for p in pk] == ["60 UC"] and "cost_usd" not in pk[0] and "sku" not in pk[0]
    assert (await api(5).get("/donate/packages?game=MC")).status_code == 404
    # bitta joyga ikkinchi o'yin qo'yilsa — birinchisi bo'shaydi
    await api(1).put("/admin/donate/games/steam", {"featured_slot": 2})
    g = (await api(5).get("/donate/games")).json()
    assert [x["slug"] for x in g["featured"]] == ["ML", "steam"]


async def test_order_via_provider_and_validation(api, ctx, monkeypatch):
    from tests.conftest import get_balance, set_balance

    row = await _provider(monkeypatch)
    async with SessionLocal() as s, s.begin():
        await dc.sync_provider(s, await s.get(DonateProvider, row.id))
    async with SessionLocal() as s:
        ml = await s.scalar(select(DonatePackage.id).where(DonatePackage.provider_sku == "sku-172"))
        pubg = await s.scalar(select(DonatePackage.id).where(DonatePackage.provider_sku == "u60"))
    await set_balance(60, 100_000)
    await api(1).put("/admin/donate/games/pubg-mobile", {"is_active": True})
    # ML: ID ham, Zone ham raqam bo'lishi shart
    assert (await api(60).post("/donate/orders", {"package_id": ml, "player_id": "12ab", "zone_id": "1"})).status_code == 400
    assert (await api(60).post("/donate/orders", {"package_id": ml, "player_id": "12345678", "zone_id": ""})).status_code == 400
    r = await api(60).post("/donate/orders", {"package_id": ml, "player_id": "12345678", "zone_id": "1234"})
    assert r.status_code == 200 and await get_balance(60) == 100_000 - 33_800
    # PUBG: faqat bitta ID, zona kerak emas
    r = await api(60).post("/donate/orders", {"package_id": pubg, "player_id": "5123456789"})
    assert r.status_code == 200, r.text


async def test_admin_provider_crud_never_returns_key(api, monkeypatch):
    async def boom(session, row):
        raise RuntimeError("tarmoq yo'q")

    monkeypatch.setattr(dc, "sync_provider", boom)  # qo'shilganda avtomatik sinxronlash — xato saqlanadi
    r = await api(1).post("/admin/donate/providers", {"name": "Yupay", "kind": "yupay", "api_key": "ypk_SUPERSECRET"})
    assert r.status_code == 200 and "SUPERSECRET" not in json.dumps(r.json()) and r.json()["key_set"] is True
    pid = r.json()["id"]
    assert "tarmoq" in (r.json().get("last_error") or "")
    assert r.json()["webhook_url"].endswith(f"/api/yupay/webhook/{pid}")
    async with SessionLocal() as s:
        raw = (await s.get(DonateProvider, pid)).key_enc
    assert "SUPERSECRET" not in raw and raw  # bazada shifrlangan
    lst = (await api(1).get("/admin/donate/providers")).json()
    assert "SUPERSECRET" not in json.dumps(lst) and len(lst["providers"]) == 1
    # kalit bo'sh yuborilsa — eskisi saqlanadi
    r = await api(1).put(f"/admin/donate/providers/{pid}", {"name": "Yupay 2", "kind": "yupay", "api_key": "", "is_active": True})
    assert r.json()["name"] == "Yupay 2" and r.json()["key_set"]
    # jurnalda kalit ko'rinmaydi
    logs = json.dumps((await api(1).get("/admin/audit")).json())
    assert "SUPERSECRET" not in logs
    assert (await api(1).post("/admin/donate/providers", {"name": "Yy", "kind": "yupay"})).status_code == 400  # kalitsiz
    assert (await api(5).get("/admin/donate/providers")).status_code == 403
    assert (await api(1).c.delete(f"/api/admin/donate/providers/{pid}", headers={"X-Dev-User": "1"})).status_code == 200


async def test_provider_webhook_uses_own_key(api, ctx):
    import hashlib
    import hmac
    import time

    from app.security import encrypt

    async with SessionLocal() as s, s.begin():
        row = DonateProvider(name="Y2", kind="yupay", key_enc=encrypt("ypk_second"))
        s.add(row)
    body = json.dumps({"merchant_order_id": "VX-D77", "status": "delivered"}).encode()
    ts = str(int(time.time()))
    canon = "\n".join((ts, "d1", "order.status_changed", hashlib.sha256(body).hexdigest())).encode()
    sig = hmac.new(b"ypk_second", canon, hashlib.sha256).hexdigest()
    hdr = {"x-yupay-timestamp": ts, "x-yupay-delivery": "d1", "x-yupay-event": "order.status_changed", "x-yupay-key-signature": sig}
    c = api(1).c
    assert (await c.post(f"/api/yupay/webhook/{row.id}", content=body, headers=hdr)).status_code == 200
    assert ("fulfil_donate", 77, "check") in ctx["jobs"]
    assert (await c.post(f"/api/yupay/webhook/{row.id + 5}", content=body, headers=hdr)).status_code == 404


async def test_features_default_on_and_toggle(api):
    me = (await api(5).get("/me")).json()
    assert me["features"]["market"] is True and me["features"]["ai"] is False and set(me["features"]) >= {"market", "tg", "arena"}
    assert (await api(1).put("/admin/settings", {"key": "feature_market", "value": "off"})).status_code == 200
    assert (await api(5).get("/me")).json()["features"]["market"] is False
    assert (await api(1).put("/admin/settings", {"key": "feature_market", "value": "on"})).status_code == 200
    assert (await api(5).get("/me")).json()["features"]["market"] is True


async def test_game_image_upload(api, client):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (600, 300), "red").save(buf, "PNG")
    await api(1).get("/me")
    r = await client.post("/api/admin/donate/games/ML/image", files={"file": ("a.png", buf.getvalue(), "image/png")}, headers={"X-Dev-User": "1"})
    assert r.status_code == 200, r.text
    url = r.json()["logo"]
    img = await client.get(url)
    assert img.status_code == 200 and img.headers["content-type"] == "image/webp"
    assert Image.open(io.BytesIO(img.content)).size == (256, 256)
    games = (await api(5).get("/donate/games")).json()
    assert games["featured"][0]["logo"] == url
    r = await client.post("/api/admin/donate/games/ML/image", files={"file": ("a.png", b"x", "image/png")}, headers={"X-Dev-User": "5"})
    assert r.status_code == 403
