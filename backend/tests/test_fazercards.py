import hashlib
import hmac
import json

import httpx

from app.api.donate import verify_fazer_signature
from app.providers.fazercards import DEFAULT_URL, FazerCardsProvider, api_url, map_order
from app.services.donate_catalog import sku_variants

BASE = "https://api.fzr.cards/api/v2"
OFFERS = {"ok": True, "kind": "topup", "category_id": "cat_ml", "name": "Mobile Legends",
          "offers": [{"offer_id": "o86", "name": "86 Diamonds", "price_usd": "1.0200"}, {"offer_id": None, "name": "x", "price_usd": "1"},
                     {"offer_id": "o0", "name": "free", "price_usd": "0"}],
          "fields": [{"key": "player_id", "label": "User ID", "type": "text"}, {"key": "server_id", "label": "Zone", "type": "text"}]}


def make(handler) -> FazerCardsProvider:
    p = FazerCardsProvider("fz_test")
    p.client = httpx.AsyncClient(base_url=BASE, transport=httpx.MockTransport(handler), headers={"X-API-Key": "fz_test"})
    return p


def router(**over):
    calls = []

    def h(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content) if req.content else None
        calls.append((req.method, req.url.path, body, dict(req.headers)))
        key = f"{req.method} {req.url.path}"
        if key in over:
            v = over[key]
            return v(req) if callable(v) else v
        if key == "GET /api/v2/topups":
            return httpx.Response(200, json={"ok": True, "items": [{"category_id": "cat_ml", "name": "Mobile Legends", "imageurl": "https://x/i.png"}],
                                             "meta": {"total": 1, "limit": 500, "next_cursor": None, "has_more": False}})
        if key == "GET /api/v2/topups/offers":
            return httpx.Response(200, json=OFFERS)
        raise AssertionError(f"kutilmagan so'rov: {key}")

    h.calls = calls
    return h


def test_api_url_normalizes():
    assert api_url("") == DEFAULT_URL
    assert api_url("https://reseller.fazercards.com/en/docs") == DEFAULT_URL
    assert api_url("https://api.fzr.cards/api/v2/") == "https://api.fzr.cards/api/v2"


async def test_catalog_shape_for_sync():
    p = make(router())
    brands = await p.catalog(force=True)
    assert len(brands) == 1
    b = brands[0]
    assert b["slug"] == "fz-mobile-legends" and b["name"] == "Mobile Legends" and b["logo_url"] == "https://x/i.png"
    skus = b["products"][0]["skus"]
    assert [s["sku_id"] for s in skus] == ["cat_ml|o86"]  # offer_id yo'q va narxi 0 bo'lganlar tashlanadi
    assert [f["key"] for f in b["products"][0]["required_fields"]] == ["player_id", "server_id"]
    assert sku_variants(skus[0], b["products"][0], "Mobile Legends") == [("cat_ml|o86", "86 Diamonds", "1.0200")]


async def test_create_uses_idempotency_and_fields():
    h = router(**{"POST /api/v2/topups/order": httpx.Response(201, json={"ok": True, "order": {"id": "ord-9002", "status": "processing"}})})
    p = make(h)
    res = await p.create("VX-D17", "cat_ml|o86", "fz-mobile-legends", "12345678", "1234")
    assert (res.status, res.ref) == ("pending", "ord-9002")
    method, path, body, headers = h.calls[-1]
    assert body == {"category_id": "cat_ml", "offer_id": "o86", "fields": {"player_id": "12345678", "server_id": "1234"}}
    assert headers["idempotency-key"] == "VX-D17"


async def test_status_needs_their_id_and_never_fails_without_it():
    h = router(**{"GET /api/v2/orders/ord-9002": httpx.Response(200, json={"ok": True, "order": {"id": "ord-9002", "status": "completed"}})})
    p = make(h)
    assert (await p.status("VX-D17")).status == "unknown"  # ID yo'q — «failed» emas (pul qaytarilib ketmasin)
    assert (await p.status("VX-D17", "ord-9002")).status == "success"


async def test_unknown_offer_fails_before_charging():
    p = make(router())
    res = await p.create("VX-D1", "cat_ml|nope", "fz-mobile-legends", "1", "")
    assert res.status == "failed" and "unknown_sku" in res.message


def test_map_order_statuses():
    assert map_order({"id": "ord-1", "status": "completed"}).status == "success"
    for s in ("failed", "refund"):
        assert map_order({"id": "ord-1", "status": s}).status == "failed"
    for s in ("processing", "created", "something_new"):
        assert map_order({"id": "ord-1", "status": s}).status == "pending"


async def test_create_http_errors():
    for code, want in ((500, "unknown"), (429, "unknown"), (409, "unknown"), (400, "failed"), (403, "failed")):
        p = make(router(**{"POST /api/v2/topups/order": httpx.Response(code, json={"ok": False, "error": "x", "code": "subscription_inactive"})}))
        assert (await p.create("VX-D2", "cat_ml|o86", "g", "1", "")).status == want, code


async def test_ping_reports_inactive_subscription():
    p = make(router(**{"GET /api/v2/me": httpx.Response(200, json={"ok": True, "login": "a", "plan": "gold", "subscriptionActive": False}),
                       "GET /api/v2/balance": httpx.Response(200, json={"ok": True, "balance": "12.5000", "currency": "USD"})}))
    r = await p.ping()
    assert r["ok"] is False and r["balance_usd"] == "12.5000"


def test_webhook_signature():
    body = b'{"event":"order.status_changed","data":{"order_id":"ord-1"}}'
    sig = "sha256=" + hmac.new(b"sekret", body, hashlib.sha256).hexdigest()
    assert verify_fazer_signature({"x-webhook-signature": sig}, body, "sekret")
    assert not verify_fazer_signature({"x-webhook-signature": sig}, body, "boshqa")
    assert not verify_fazer_signature({"x-webhook-signature": sig}, body, "")  # sir qo'yilmagan — hech narsa qabul qilinmaydi
    assert not verify_fazer_signature({}, body, "sekret")


def test_http_kind_with_fazercards_url_is_auto_detected():
    from types import SimpleNamespace

    from app.security import encrypt
    from app.services.donate_catalog import build_provider

    row = SimpleNamespace(kind="http", base_url="https://api.fzr.cards/api/v2", key_enc=encrypt("k"), config={})
    assert isinstance(build_provider(row), FazerCardsProvider)
