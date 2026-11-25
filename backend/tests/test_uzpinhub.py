import json

import httpx
import pytest

from app.providers.base import ProviderAuthError
from app.providers.uzpinhub import DEFAULT_URL, UzpinhubProvider, api_url, map_order
from app.services.donate_catalog import sku_variants

GID = "6f6868a6-cc8f-452c-ac96-a5c281769397"
PID = "fbe54bc3-0000-0000-0000-000000000086"
VGID = "992959b2-0000-0000-0000-000000000001"
VPID = "aaaa0000-0000-0000-0000-000000000100"


def router(**over):
    calls = []

    def h(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else None
        calls.append((req.method, req.url.path, body, dict(req.headers)))
        key = f"{req.method} {req.url.path}"
        if key in over:
            v = over[key]
            return v(req) if callable(v) else v
        page = {"page": 1, "page_size": 100, "total": 1, "total_pages": 1, "next_page": None, "prev_page": None}
        if key == "GET /api/game/topup-games":
            return httpx.Response(200, json={**page, "data": [
                {"id": GID, "name": "Mobile Legends (Global)", "image_url": "https://api.uzpinhub.uz/uploads/x.jpg"},
                {"id": "tg", "name": "Telegram Stars"}]})
        if key == f"GET /api/game/games/{GID}/products":
            return httpx.Response(200, json={"game": {"id": GID}, "products": [{"id": PID, "name": "78 + 8 Diamonds", "price": "1.204"},
                                                                                {"id": "z", "name": "free", "price": "0"}]})
        if key == f"GET /api/game/topup-games/{GID}/required-fields":
            return httpx.Response(200, json=["userid", "serverid"])
        if key == "GET /api/game/simple-games":
            return httpx.Response(200, json={**page, "data": [{"id": VGID, "name": "Roblox (Global)"}]})
        if key == f"GET /api/game/simple-game-products/{VGID}":
            return httpx.Response(200, json=[{"id": VPID, "name": "100 Robux", "price": "1.500", "stock": 7}])
        raise AssertionError(f"kutilmagan so'rov: {key}")

    h.calls = calls
    return h


def make(handler) -> UzpinhubProvider:
    p = UzpinhubProvider("k", callback_url="https://bot.example/api/uzpinhub/webhook/9")
    p.client = httpx.AsyncClient(base_url=DEFAULT_URL + "/", transport=httpx.MockTransport(handler), headers={"X-API-Key": "k"})
    return p


def test_api_url():
    assert api_url("") == DEFAULT_URL
    assert api_url("https://api.uzpinhub.uz/api/") == "https://api.uzpinhub.uz/api"
    assert api_url("https://evil.example/api") == DEFAULT_URL  # kalit begona manzilga yuborilmaydi


async def test_catalog_shape():
    brands = await make(router()).catalog(force=True)
    slugs = {b["slug"]: b for b in brands}
    assert set(slugs) == {"uz-mobile-legends-global", "uz-roblox-global"}  # Telegram — alohida bo'limda
    ml = slugs["uz-mobile-legends-global"]["products"][0]
    assert [f["key"] for f in ml["required_fields"]] == ["player_id", "server_id"]
    assert [s["sku_id"] for s in ml["skus"]] == [f"t|{PID}|{GID}"]  # narxi 0 bo'lgani tashlanadi
    assert sku_variants(ml["skus"][0], ml, "Mobile Legends (Global)")[0][2] == "1.204"
    rb = slugs["uz-roblox-global"]["products"][0]
    assert rb["required_fields"] == [] and rb["skus"][0]["sku_id"] == f"v|{VPID}" and rb["skus"][0]["stock"] == 7


async def test_create_topup_and_status_by_external_id():
    h = router(**{
        "POST /api/order/topup/buy": httpx.Response(200, json={"order_id": "o-1", "status": "processing", "amount": "1.204"}),
        "GET /api/user/profile/orders": httpx.Response(200, json={"data": [{"id": "o-1", "external_order_id": "VX-D5"}], "next_page": None}),
        "GET /api/user/profile/orders/o-1": httpx.Response(200, json={"id": "o-1", "status": "completed"}),
        "GET /api/user/profile/orders/o-1/values": httpx.Response(200, json=[]),
    })
    p = make(h)
    r = await p.create("VX-D5", f"t|{PID}|{GID}", "uz-mobile-legends-global", "12345678", "2051")
    assert (r.status, r.ref) == ("pending", "o-1")
    body = h.calls[-1][2]
    assert body == {"external_order_id": "VX-D5", "game_product_id": PID, "player_id": "12345678", "server_id": "2051",
                    "callback_url": "https://bot.example/api/uzpinhub/webhook/9"}
    p2 = make(h)  # yangi nusxa (server qayta ishga tushgan) — ref xotirada yo'q, ro'yxatdan topiladi
    assert (await p2.status("VX-D5")).status == "success"


async def test_voucher_code_delivered():
    h = router(**{
        "POST /api/order/simple/buy": httpx.Response(200, json={"order_id": "o-2", "status": "completed"}),
        "GET /api/user/profile/orders/o-2/values": httpx.Response(200, json=["ABCD-EFGH-1234"]),
    })
    r = await make(h).create("VX-D6", f"v|{VPID}", "uz-roblox-global", "", "")
    assert r.status == "success" and r.artifact == {"code": "ABCD-EFGH-1234"}
    assert h.calls[0][2] == {"external_order_id": "VX-D6", "game_product_id": VPID, "quantity": 1}


async def test_auth_failure_stops_all_further_key_requests():
    h = router(**{"GET /api/user/profile": httpx.Response(401, json={"success": False, "message": "bad key"})})
    p = make(h)
    r = await p.ping()
    assert not r["ok"] and r["status"] == 401
    n = len(h.calls)
    assert (await p.ping())["ok"] is False and len(h.calls) == n  # ikkinchi marta tarmoqqa chiqilmaydi (IP ban xavfi)
    assert (await p.create("VX-D7", f"t|{PID}|{GID}", "g", "1", "")).status == "failed" and len(h.calls) == n
    assert (await p.status("VX-D7")).status == "unknown" and len(h.calls) == n
    with pytest.raises(ProviderAuthError):
        await p._get("user/profile", auth=True)


async def test_check_player():
    h = router(**{"POST /api/order/topup/check_game_ids": httpx.Response(200, json={"gamer_name": "AzizPro"})})
    p = make(h)
    await p.catalog(force=True)
    assert await p.check_player("uz-mobile-legends-global", "12345678", "2051") == "AzizPro"
    h2 = router(**{"POST /api/order/topup/check_game_ids": httpx.Response(400, json={"success": False, "message": "not found"})})
    p2 = make(h2)
    await p2.catalog(force=True)
    assert await p2.check_player("uz-mobile-legends-global", "1", "1") is None
    assert await p2.check_player("ML", "1", "1") == ""  # bog'lanmagan o'yin — tekshirib bo'lmaydi, to'smaydi


def test_map_order():
    assert map_order({"order_id": "a", "status": "completed"}).status == "success"
    assert map_order({"order_id": "a", "status": "failed", "error_message": "x"}).status == "failed"
    for s in ("processing", "created", "new_status"):
        assert map_order({"order_id": "a", "status": s}).status == "pending"


async def test_admin_detects_kind_by_url_and_webhook(api, monkeypatch):
    from app.db import SessionLocal
    from app.models import DonateOrder, DonatePackage
    from app.services import donate_catalog

    async def no_sync(session, row):
        return {"games": 0, "packages": 0, "new_games": []}

    monkeypatch.setattr(donate_catalog, "sync_provider", no_sync)
    p = (await api(1).post("/admin/donate/providers", json={"name": "API 3", "api_key": "abc", "base_url": "https://api.uzpinhub.uz/api/"})).json()
    assert p["kind"] == "uzpinhub" and p["kind_label"] == "Donat API" and p["host"] is None
    async with SessionLocal() as s, s.begin():
        pk = DonatePackage(game="ML", name="86", diamonds=86, price=18100, provider_sku=f"t|{PID}|{GID}", provider_id=p["id"], source="api")
        s.add(pk)
        await s.flush()
        await api(5).get("/me")
        s.add(DonateOrder(user_id=5, package_id=pk.id, game="ML", title="86", player_id="1", price=18100, status="processing", provider_ref="3fa85f64-5717-4562-b3fc-2c963f66afa6"))
    sent = []

    async def fake_enqueue(*a, **k):
        sent.append(a)

    monkeypatch.setattr("app.api.donate.enqueue", fake_enqueue)
    r = await api(1).post(f"/uzpinhub/webhook/{p['id']}", json={"order_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6", "status": "completed"})
    assert r.status_code == 200 and sent and sent[0][0] == "fulfil_donate" and sent[0][2] == "check"
    assert (await api(1).post("/uzpinhub/webhook/99999", json={"order_id": "o-9"})).status_code == 404
