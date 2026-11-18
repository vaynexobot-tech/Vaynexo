import hashlib
import hmac
import json
import time

import httpx
import pytest

from app.providers.yupay import YupayProvider, map_order

SKU = "01a042ce-7bf4-7880-83bc-d9688237c93b"
CATALOG = {"brands": [
    {"slug": "mobile-legends", "name": "Mobile Legends", "products": [{
        "name": "Diamonds", "product_id": "p1", "slug": "mobile-legends",
        "required_fields": [{"key": "player_id", "required": True}, {"key": "server_id", "required": True}],
        "skus": [{"sku_id": SKU, "name": "172 Diamonds", "kind": "fixed", "price_usd": "2.55", "stock": None}]}]},
    {"slug": "mobile-legends-ru", "name": "Mobile Legends RU", "products": []},
    {"slug": "magic-chess-gogo", "name": "Magic Chess", "products": []},
]}


def make(handler) -> YupayProvider:
    p = YupayProvider("ypk_test")
    p.client = httpx.AsyncClient(base_url="https://api.yupay.uz/merchant/v1", transport=httpx.MockTransport(handler),
                                 headers={"Authorization": "Bearer ypk_test"})
    return p


def router(**over):
    calls = []

    def h(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else None
        calls.append((req.method, req.url.path, body))
        key = f"{req.method} {req.url.path}"
        if key in over:
            v = over[key]
            return v(req) if callable(v) else v
        if key == "GET /merchant/v1/catalog":
            return httpx.Response(200, json=CATALOG)
        raise AssertionError(f"kutilmagan so'rov: {key}")

    h.calls = calls
    return h


async def test_brand_detection_and_player_check():
    h = router(**{"POST /merchant/v1/validate/player": httpx.Response(200, json={"status": "valid", "name": "Aziz"})})
    p = make(h)
    assert await p.brand_slug("ML") == "mobile-legends"  # RU variant tanlanmaydi
    assert await p.brand_slug("MC") == "magic-chess-gogo"
    assert await p.check_player("ML", "12345678", "1234") == "Aziz"
    assert h.calls[-1][2] == {"brand": "mobile-legends", "player_id": "12345678", "server_id": "1234"}


@pytest.mark.parametrize("resp,expected", [
    ({"status": "invalid"}, None),
    ({"status": "valid", "reason": "wrong_region"}, None),
    ({"status": "error"}, ""),
    ({"status": "unsupported"}, ""),
])
async def test_player_check_verdicts(resp, expected):
    p = make(router(**{"POST /merchant/v1/validate/player": httpx.Response(200, json=resp)}))
    assert await p.check_player("ML", "12345678", "") == expected


async def test_player_check_never_blocks_on_failure():
    p = make(router(**{"POST /merchant/v1/validate/player": httpx.Response(503)}))
    assert await p.check_player("ML", "12345678", "1234") == ""  # tekshirib bo'lmadi — yo'l qo'yiladi


async def test_create_order_success_and_payload():
    h = router(**{"POST /merchant/v1/orders": httpx.Response(201, json={"status": "delivered", "order_id": "O1"})})
    r = await make(h).create("VX-D7", SKU.upper(), "ML", "12345678", "1234")
    assert r.status == "success" and r.ref == "O1"
    method, path, body = h.calls[-1]
    assert body == {"merchant_order_id": "VX-D7", "sku_id": SKU, "expected_price": "2.55",
                    "fulfillment_data": {"player_id": "12345678", "server_id": "1234"}}


@pytest.mark.parametrize("resp,status,needle", [
    (httpx.Response(201, json={"status": "paid", "order_id": "O"}), "pending", ""),
    (httpx.Response(201, json={"status": "fulfilling", "order_id": "O"}), "pending", ""),
    (httpx.Response(201, json={"status": "yangi-holat", "order_id": "O"}), "pending", ""),  # noma'lum — jarayonda
    (httpx.Response(409, json={"code": "insufficient_deposit"}), "failed", "depozit"),
    (httpx.Response(422, json={"code": "price_changed", "current_price": "3.00"}), "failed", "price_changed"),
    (httpx.Response(404, json={"code": "item_unavailable", "reason": "out_of_stock"}), "failed", "mavjud emas"),
    (httpx.Response(401, json={"code": "invalid_credentials"}), "failed", "kaliti"),
    (httpx.Response(429), "unknown", ""),
    (httpx.Response(502), "unknown", ""),
])
async def test_create_order_outcomes(resp, status, needle):
    r = await make(router(**{"POST /merchant/v1/orders": resp})).create("VX-D7", SKU, "ML", "12345678", "1234")
    assert r.status == status and needle in r.message


async def test_create_unknown_sku_is_refunded():
    r = await make(router()).create("VX-D7", "ML_172", "ML", "12345678", "1234")
    assert r.status == "failed" and "unknown_sku" in r.message


async def test_order_id_reused_reads_existing_order():
    h = router(**{"POST /merchant/v1/orders": httpx.Response(409, json={"code": "order_id_reused"}),
                  "GET /merchant/v1/orders/VX-D7": httpx.Response(200, json={"status": "delivered", "order_id": "O9"})})
    r = await make(h).create("VX-D7", SKU, "ML", "12345678", "1234")
    assert r.status == "success" and r.ref == "O9"


def test_map_order_statuses():
    assert map_order({"status": "delivered"}).status == "success"
    assert map_order({"status": "fulfilling", "failure_reason": "fulfillment_delayed"}).status == "pending"  # kutish, qaytarish emas
    assert map_order({"status": "failed", "failure_reason": "fulfillment_failed_refunded"}).status == "failed"
    assert map_order({"status": "failed", "price_usd": "2.55", "refunded_usd": "2.55"}).status == "failed"
    # qisman qaytarilgan — foydalanuvchiga pul qaytarilmaydi, admin ko'radi
    assert map_order({"status": "failed", "failure_reason": "fulfillment_failed", "price_usd": "2.55", "refunded_usd": "0.00"}).status == "unknown"


async def test_status_404_and_errors():
    assert (await make(router(**{"GET /merchant/v1/orders/VX-D1": httpx.Response(404)})).status("VX-D1")).status == "failed"
    assert (await make(router(**{"GET /merchant/v1/orders/VX-D1": httpx.Response(500)})).status("VX-D1")).status == "unknown"


async def test_ping_messages():
    ok = await make(router(**{"GET /merchant/v1/me": httpx.Response(200, json={"balance_usd": "16.54", "title": "ACME", "status": "active"})})).ping()
    assert ok["ok"] and ok["balance_usd"] == "16.54"
    bad = await make(router(**{"GET /merchant/v1/me": httpx.Response(401, json={"code": "invalid_credentials"})})).ping()
    assert not bad["ok"] and "401" in bad["error"]
    ip = await make(router(**{"GET /merchant/v1/me": httpx.Response(403, json={"code": "ip_not_allowed"})})).ping()
    assert not ip["ok"] and "IP" in ip["error"]


async def test_skus_for_filters_game():
    skus = await make(router()).skus_for("ML")
    assert [s["sku_id"] for s in skus] == [SKU] and skus[0]["price_usd"] == "2.55"


def _sign(key, ts, delivery, event, body):
    canon = "\n".join((ts, delivery, event, hashlib.sha256(body).hexdigest())).encode()
    return hmac.new(key.encode(), canon, hashlib.sha256).hexdigest()


async def test_webhook_signature_and_enqueue(api, ctx, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "donate_provider_key", "ypk_secret")
    body = json.dumps({"merchant_order_id": "VX-D42", "order_id": "x", "status": "delivered", "at": "2026-01-01T00:00:00Z"}).encode()
    ts = str(int(time.time()))
    hdr = {"x-yupay-timestamp": ts, "x-yupay-delivery": "d1", "x-yupay-event": "order.status_changed",
           "x-yupay-key-signature": _sign("ypk_secret", ts, "d1", "order.status_changed", body), "content-type": "application/json"}
    c = api(1).c
    bad = await c.post("/api/yupay/webhook", content=body, headers={**hdr, "x-yupay-key-signature": "00"})
    assert bad.status_code == 401
    ok = await c.post("/api/yupay/webhook", content=body, headers=hdr)
    assert ok.status_code == 200 and ("fulfil_donate", 42, "check") in ctx["jobs"]
    old = str(int(time.time()) - 4000)
    stale = {**hdr, "x-yupay-timestamp": old, "x-yupay-key-signature": _sign("ypk_secret", old, "d1", "order.status_changed", body)}
    assert (await c.post("/api/yupay/webhook", content=body, headers=stale)).status_code == 401
    monkeypatch.setattr(settings, "donate_provider_key", "")
    assert (await c.post("/api/yupay/webhook", content=body, headers=hdr)).status_code == 401  # kalit yo'q — qabul qilinmaydi


async def test_admin_yupay_endpoints(api, monkeypatch):
    from app import providers
    from app.config import settings

    monkeypatch.setattr(settings, "donate_provider", "yupay")
    monkeypatch.setattr(settings, "donate_provider_key", "ypk_secret")
    info = (await api(1).get("/admin/donate/provider")).json()
    assert info["live"] and info["yupay"] and info["webhook_url"].endswith("/api/yupay/webhook")
    assert "ypk_secret" not in json.dumps(info)
    prov = make(router(**{"GET /merchant/v1/me": httpx.Response(200, json={"balance_usd": "9.99", "title": "T", "status": "active"})}))
    providers.set_provider(prov)
    try:
        t = (await api(1).post("/admin/donate/provider/test")).json()
        assert t["ok"] and t["balance_usd"] == "9.99"
        skus = (await api(1).get("/admin/donate/yupay/skus?game=ML")).json()
        assert skus and skus[0]["sku_id"] == SKU
        assert (await api(5).get("/admin/donate/yupay/skus")).status_code == 403
    finally:
        from app.providers.mock import MockProvider

        providers.set_provider(MockProvider())


async def test_mode_never_echoes_value(api, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "donate_provider", "ypk_SECRETKEY123")
    r = (await api(1).get("/admin/donate/provider")).json()
    assert "SECRETKEY" not in json.dumps(r) and r["mode"] == "noto'g'ri" and r["mode_invalid"] and not r["live"]
