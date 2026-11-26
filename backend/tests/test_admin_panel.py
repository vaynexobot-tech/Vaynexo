from app.db import SessionLocal
from app.models import DonateGame, DonateOrder, DonatePackage, DonateProvider, TgOrder, User, Withdrawal


async def _providers():
    async with SessionLocal() as s, s.begin():
        y = DonateProvider(name="Yupay", kind="yupay", base_url="", key_enc="x", config={}, balance_usd="142.30")
        f = DonateProvider(name="FazerCards", kind="fazercards", base_url="", key_enc="x", config={}, balance_usd="3.10")
        s.add_all([y, f])
    return y.id, f.id


async def _ml_two_providers():
    y, f = await _providers()
    async with SessionLocal() as s, s.begin():
        g = await s.get(DonateGame, "ML")
        g.provider_id, g.brand_slug, g.brands = y, "mobile-legends", {str(y): "mobile-legends"}
        s.add(DonateGame(slug="fz-mobile-legends-global", name="Mobile Legends (Global)", provider_id=f, brand_slug="fz-mobile-legends-global",
                         brands={str(f): "fz-mobile-legends-global"}, is_active=False, fields=[]))
        s.add_all([
            DonatePackage(game="ML", name="86 Diamonds (78 + 8)", diamonds=78, bonus=8, price=18100, cost_usd="1.28", provider_sku="y86", provider_id=y, source="api"),
            DonatePackage(game="ML", name="172 Diamonds (156 + 16)", diamonds=156, bonus=16, price=36000, cost_usd="2.55", provider_sku="y172", provider_id=y, source="api"),
            DonatePackage(game="fz-mobile-legends-global", name="78 + 8 Diamonds", diamonds=78, bonus=8, price=14400, cost_usd="1.02",
                          provider_sku="c|o86", provider_id=f, source="api"),
            DonatePackage(game="fz-mobile-legends-global", name="156 + 16 Diamonds", diamonds=156, bonus=16, price=28800, cost_usd="2.04",
                          provider_sku="c|o172", provider_id=f, source="api"),
        ])
    return y, f


async def test_dashboard_and_queue_actions(api):
    y, f = await _providers()
    async with SessionLocal() as s, s.begin():
        s.add(User(id=777, first_name="Jasur", username="jasur", balance=0))
        await s.flush()
        s.add(Withdrawal(user_id=777, amount=300_000, card_number="8600123412344471", card_holder="J", status="pending"))
        s.add(TgOrder(user_id=777, kind="gift", title="Gift 🧸", target_username="dilshod", price=10_000, status="processing", details={}))
    r = (await api(1).get("/admin/dashboard")).json()
    assert {p["name"]: p["low"] for p in r["providers"]} == {"Yupay": False, "FazerCards": True}
    kinds = {i["kind"] for i in r["queue"]}
    assert {"withdraw", "tg"} <= kinds
    w = next(i for i in r["queue"] if i["kind"] == "withdraw")
    assert w["copy"] == "8600123412344471" and "4471" in w["sub"]
    assert r["bot"]["guests"] == 0 and "open" in r["bot"]
    assert (await api(5).get("/admin/dashboard")).status_code == 403
    tg = next(i for i in r["queue"] if i["kind"] == "tg")
    assert (await api(1).post(f"/admin/queue/tg/{tg['id']}", json={"action": "refund"})).json()["ok"]
    assert (await api(1).post(f"/admin/queue/withdraw/{w['id']}", json={"action": "nope"})).status_code == 400


async def test_catalog_compare_link_switch(api):
    y, f = await _ml_two_providers()
    r = (await api(1).get("/admin/catalog/games?state=active")).json()
    ml = next(x for x in r["items"] if x["slug"] == "ML")
    assert ml["cheaper"]["provider"] == "FazerCards" and ml["cheaper"]["pct"] == -20 and not ml["cheaper"]["linked"]
    assert r["counts"]["cheaper"] == 1
    # bog'lash: FazerCards paketlari ML ga o'tadi, sotuv hali Yupay'da
    assert (await api(1).post("/admin/catalog/games/ML/link", json={"from_slug": "fz-mobile-legends-global"})).json()["ok"]
    user_pk = (await api(5).get("/donate/packages?game=ML")).json()
    assert {p["name"] for p in user_pk} == {"86 Diamonds (78 + 8)", "172 Diamonds (156 + 16)"}
    d = (await api(1).get("/admin/catalog/games/ML")).json()
    assert any(p["provider"] == "FazerCards" and p["linked"] and p["pct"] == -20 for p in d["providers"])
    assert all(p["profit"] is not None for p in d["packages"])
    # almashtirish: endi foydalanuvchiga FazerCards paketlari
    assert (await api(1).post("/admin/catalog/games/ML/provider", json={"provider_id": f})).json()["ok"]
    user_pk = (await api(5).get("/donate/packages?game=ML")).json()
    assert {p["name"] for p in user_pk} == {"78 + 8 Diamonds", "156 + 16 Diamonds"}
    async with SessionLocal() as s:
        prov = await s.get(DonateProvider, f)
        assert prov.config["map"] == {"fz-mobile-legends-global": "ML"}
        assert await s.get(DonateGame, "fz-mobile-legends-global") is None
        g = await s.get(DonateGame, "ML")
        assert g.brand_slug == "fz-mobile-legends-global"
    # bog'lanmagan API'ga almashtirib bo'lmaydi
    assert (await api(1).post("/admin/catalog/games/ML/provider", json={"provider_id": 999})).status_code == 409


async def test_sync_respects_selected_provider_and_map(api):
    """Ikkinchi API sinxronlansa ham o'yin egasi o'zgarmaydi; xarita bo'yicha paketlar shu o'yinga yoziladi."""
    from app.services import donate_catalog

    y, f = await _ml_two_providers()
    await api(1).post("/admin/catalog/games/ML/link", json={"from_slug": "fz-mobile-legends-global"})

    class P:
        async def catalog(self, force=False):
            return [{"slug": "fz-mobile-legends-global", "name": "Mobile Legends (Global)", "products": [{"name": "x",
                     "required_fields": [{"key": "player_id"}], "skus": [{"sku_id": "c|o86", "name": "78 + 8 Diamonds", "kind": "fixed", "price_usd": "0.99"}]}]}]

    async with SessionLocal() as s, s.begin():
        row = await s.get(DonateProvider, f)
        donate_catalog._instances[f] = (__import__("hashlib").sha1(f"{row.kind}|{row.base_url}|{row.key_enc}|{row.config}".encode()).hexdigest(), P())
        await donate_catalog.sync_provider(s, row)
    async with SessionLocal() as s:
        g = await s.get(DonateGame, "ML")
        assert g.provider_id == y  # Yupay hali ham sotadi
        p = await s.scalar(__import__("sqlalchemy").select(DonatePackage).where(DonatePackage.provider_sku == "c|o86"))
        assert p.game == "ML" and p.cost_usd == "0.99"
        assert await s.get(DonateGame, "fz-mobile-legends-global") is None


async def test_orders_feed_and_search(api):
    async with SessionLocal() as s, s.begin():
        s.add(User(id=778, first_name="A", username="aziz", balance=0))
        await s.flush()
        pk = DonatePackage(game="ML", name="86", diamonds=86, price=18100, provider_sku="x")
        s.add(pk)
        await s.flush()
        s.add(DonateOrder(user_id=778, package_id=pk.id, game="ML", title="86 💎", player_id="84512937", zone_id="2051", price=18100, status="review", error="x"))
        s.add(DonateOrder(user_id=778, package_id=pk.id, game="ML", title="86 💎", player_id="1", price=18100, status="done"))
    r = (await api(1).get("/admin/orders?state=attention")).json()
    assert [i["status"] for i in r["items"]] == ["review"] and r["counts"]["attention"] == 1
    assert r["items"][0]["actions"][0][0] == "retry"
    assert len((await api(1).get("/admin/orders?q=@aziz")).json()["items"]) == 2
    assert len((await api(1).get("/admin/orders?q=84512937")).json()["items"]) == 1
    assert (await api(1).get("/admin/orders?state=done&kind=donate")).json()["items"][0]["label"] == "Yetkazildi"


async def test_bot_open_and_guests(api):
    from app.services import launch

    try:
        assert (await api(1).post("/admin/bot/open", json={"open": False})).json()["open"] is False
        assert (await api(1).post("/admin/bot/guests", json={"id": 5551234})).json()["count"] == 1
        assert [g["id"] for g in (await api(1).get("/admin/bot/guests")).json()] == [5551234]
        assert await launch.allowed(5551234)
        assert (await api(1).post("/admin/bot/guests", json={"id": 5551234, "add": False})).json()["count"] == 0
        assert (await api(5).post("/admin/bot/open", json={"open": True})).status_code == 403
    finally:
        await launch.set_open(True)
        await launch.set_guests(set())


async def test_provider_kind_auto_detected_and_names_hidden(api, monkeypatch):
    """API qo'shishda sayt tanlanmaydi: ypk_ → yupay, aks holda FazerCards; ro'yxatda sayt nomi/manzili ko'rinmaydi."""
    from app.services import donate_catalog

    async def no_sync(session, row):
        return {"games": 0, "packages": 0, "new_games": []}

    monkeypatch.setattr(donate_catalog, "sync_provider", no_sync)
    a = (await api(1).post("/admin/donate/providers", json={"name": "API 1", "api_key": "ypk_test123"})).json()
    b = (await api(1).post("/admin/donate/providers", json={"name": "API 2", "api_key": "fz_abc", "base_url": "https://api.fzr.cards/api/v2"})).json()
    assert (a["kind"], b["kind"]) == ("yupay", "fazercards")
    for p in (a, b):
        assert p["kind_label"] == "Donat API" and p["host"] is None and p["base_url"] == ""
    # manzilsiz noma'lum kalit — taxmin qilinmaydi (kalit boshqa saytga yuborilmasin)
    r = await api(1).post("/admin/donate/providers", json={"name": "Uzpin", "api_key": "secret123"})
    assert r.status_code == 400 and r.json()["error"] == "need_url"
    # noto'g'ri turga tushgan API: tahrirlashda manzil kiritilsa — turi tuzatiladi
    fixed = (await api(1).put(f"/admin/donate/providers/{b['id']}", json={"name": "Uzpin", "kind": "fazercards", "base_url": "https://api.uzpinhub.uz/api/"})).json()
    assert fixed["kind"] == "uzpinhub" and fixed["last_error"] is None


async def test_delivery_eta_only_from_real_data(api):
    """Yetkazish vaqti taxmin emas: kamida 5 ta avtomatik yetkazilgan buyurtma bo'lsagina ko'rsatiladi."""
    from datetime import datetime, timedelta, timezone

    from app.db import SessionLocal
    from app.models import DonateOrder, DonatePackage, DonateProvider

    assert (await api(5).get("/donate/games/ML")).json()["eta_seconds"] is None
    async with SessionLocal() as s, s.begin():
        prov = DonateProvider(name="API 1", kind="yupay", base_url="", key_enc="x", config={})
        s.add(prov)
        await s.flush()
        pk = DonatePackage(game="ML", name="86", diamonds=86, price=18100, provider_sku="x", provider_id=prov.id, source="api")
        s.add(pk)
        await api(5).get("/me")
        await s.flush()
        t0 = datetime.now(timezone.utc) - timedelta(hours=1)
        for sec in (20, 25, 30, 35, 400):  # mediana 30 (bitta kechikkan buyurtma natijani buzmaydi)
            s.add(DonateOrder(user_id=5, package_id=pk.id, game="ML", title="86", player_id="1", price=1, status="done", attempts=1,
                              created_at=t0, finished_at=t0 + timedelta(seconds=sec)))
    assert (await api(5).get("/donate/games/ML")).json()["eta_seconds"] == 30


async def test_api_routing_page_and_bulk(api):
    from tests.conftest import set_balance

    await set_balance(1, 0)
    y, f = await _ml_two_providers()
    # FazerCards paketlarini ML'ga bog'laymiz (2 API bitta o'yinda)
    assert (await api(1).post("/admin/catalog/games/ML/link", {"from_slug": "fz-mobile-legends-global"})).status_code == 200
    r = (await api(1).get("/admin/catalog/routing")).json()
    ml = next(g for s in r["sections"] for g in s["games"] if g["slug"] == "ML")
    assert ml["provider_id"] == y and {o["provider_id"] for o in ml["options"]} == {y, f}
    # hammasini FazerCards'ga o'tkazish
    res = (await api(1).post("/admin/catalog/routing/bulk", {"provider_id": f})).json()
    assert res["changed"] == 1
    async with SessionLocal() as s:
        assert (await s.get(DonateGame, "ML")).provider_id == f
    # foydalanuvchiga endi faqat FazerCards paketlari ko'rinadi
    pk = (await api(1).get("/donate/packages?game=ML")).json()
    assert {p["provider_id"] for p in pk} == {f}
    assert (await api(5).get("/admin/catalog/routing")).status_code in (401, 403)
