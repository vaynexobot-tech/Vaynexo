"""YuPay Merchant API (https://reseller.yupay.uz/uz/docs) — donat avtomatik yetkazish.

Asosiy qoidalar (hujjatdan):
- Bazaviy manzil https://api.yupay.uz/merchant/v1 ; sarlavha `Authorization: Bearer ypk_…`
- SINOV MUHITI YO'Q: POST /orders haqiqiy xarid qiladi va depozitdan yechadi.
- Pul — satr (USD, «16.54»). Buyurtma `merchant_order_id` bo'yicha idempotent: takroriy yuborish ikkinchi yechim bermaydi.
- Holat: paid → fulfilling → delivered | failed. Noma'lum holat — hali jarayonda deb hisoblanadi.
- `fulfillment_delayed` tugagan holat emas: kutish kerak, qayta buyurtma ham, qaytarish ham mumkin emas.
"""

import logging
import time
from decimal import Decimal, InvalidOperation
from urllib.parse import quote

import httpx

from app.providers.base import ProviderResult

log = logging.getLogger(__name__)

DEFAULT_URL = "https://api.yupay.uz/merchant/v1"


def api_url(base_url: str) -> str:
    """Faqat Merchant API manzili qabul qilinadi; kabinet/sayt sahifasi kiritilsa — standart API manzili."""
    u = (base_url or "").strip().rstrip("/")
    return u if u.startswith("https://") and "/merchant/" in u + "/" else DEFAULT_URL
GAME_KEYWORD = {"ML": "mobile-legends", "MC": "magic-chess"}
CATALOG_TTL = 300


def _code(r: httpx.Response) -> str:
    try:
        return str(r.json().get("code") or "")
    except (ValueError, AttributeError):
        return ""


def _dec(v) -> Decimal | None:
    try:
        return Decimal(str(v))
    except (InvalidOperation, TypeError):
        return None


VOUCHER_KEYS = ("code", "pin", "serial", "link")


def voucher_artifact(data: dict) -> dict | None:
    """Buyurtmadan vaucher kodini ajratib olish (faqat buyurtmani o'qish beradi; vebhukda kod bo'lmaydi)."""
    d = data.get("delivery") or {}
    art = d.get("artifact") if isinstance(d, dict) else None
    if not isinstance(art, dict):
        return None
    out = {k: str(art[k])[:500] for k in VOUCHER_KEYS if art.get(k) not in (None, "")}
    return out or None


def map_order(data: dict) -> ProviderResult:
    """Yupay buyurtma javobini bizning natijaga aylantirish."""
    status = str(data.get("status") or "").lower()
    ref = str(data.get("order_id") or "") or None
    reason = data.get("failure_reason")
    if status == "delivered":
        return ProviderResult("success", ref=ref, artifact=voucher_artifact(data))
    if status == "failed":
        price, back = _dec(data.get("price_usd")), _dec(data.get("refunded_usd"))
        if reason == "fulfillment_failed_refunded" or (price is not None and back is not None and price > 0 and back >= price):
            return ProviderResult("failed", ref=ref, message=f"yupay: {reason or 'failed'} (to'liq qaytarilgan)")
        # qisman qaytarilgan / qo'llab-quvvatlash yopgan — admin ko'rib chiqadi
        return ProviderResult("unknown", ref=ref, message=f"yupay: {reason or 'failed'} (qaytarish to'liq emas)")
    # paid, fulfilling, fulfillment_delayed va yangi noma'lum holatlar — hali jarayonda
    return ProviderResult("pending", ref=ref, message=str(reason or status))


class YupayProvider:
    manual = False

    def __init__(self, api_key: str, base_url: str = "", timeout: float = 25.0):
        from app.config import settings

        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=api_url(base_url), timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        self._catalog: list[dict] | None = None
        self._catalog_at = 0.0

    # ------------------------------------------------------------------ katalog
    async def catalog(self, force: bool = False) -> list[dict]:
        if force or self._catalog is None or time.monotonic() - self._catalog_at > CATALOG_TTL:
            r = await self.client.get("/catalog")
            if r.status_code in (401, 403):
                raise RuntimeError("API kalit noto'g'ri yoki bekor qilingan (Yupay kabinetida yangi kalit yarating)")
            r.raise_for_status()
            try:
                data = r.json()
            except ValueError:
                raise RuntimeError(f"Yupay JSON o'rniga sahifa qaytardi ({r.status_code}) — manzilni bo'sh qoldiring") from None
            self._catalog = data.get("brands") or []
            self._catalog_at = time.monotonic()
        return self._catalog

    def _brands_for(self, game: str, brands: list[dict]) -> list[dict]:
        env = {"ML": self.settings.donate_brand_ml, "MC": self.settings.donate_brand_mc}.get(game, "")
        if env:
            return [b for b in brands if b.get("slug") == env]
        kw = GAME_KEYWORD.get(game, "")
        found = [b for b in brands if kw and kw in str(b.get("slug", "")) and "ru" not in str(b.get("slug", "")).split("-")[2:]]
        return sorted(found, key=lambda b: len(str(b.get("slug", ""))))

    async def brand_slug(self, game: str) -> str | None:
        try:
            found = self._brands_for(game, await self.catalog())
        except (httpx.HTTPError, ValueError):
            return None
        return found[0]["slug"] if found else None

    @staticmethod
    def _find_sku(brands: list[dict], sku_id: str) -> tuple[dict, dict] | None:
        want = sku_id.replace("-", "").lower()
        for b in brands:
            for p in b.get("products") or []:
                for s in p.get("skus") or []:
                    if str(s.get("sku_id", "")).replace("-", "").lower() == want:
                        return p, s
        return None

    async def skus_for(self, game: str) -> list[dict]:
        """Admin SKU tanlashi uchun tekis ro'yxat."""
        out = []
        for b in self._brands_for(game, await self.catalog(force=True)):
            for p in b.get("products") or []:
                for s in p.get("skus") or []:
                    out.append({"sku_id": s.get("sku_id"), "name": s.get("name") or p.get("name"), "product": p.get("name"),
                                "brand": b.get("slug"), "kind": s.get("kind"), "price_usd": s.get("price_usd"),
                                "stock": s.get("stock")})
        return out

    # ------------------------------------------------------------------ hisob
    async def ping(self) -> dict:
        t0 = time.monotonic()
        try:
            r = await self.client.get("/me")
        except httpx.HTTPError as e:
            return {"ok": False, "error": f"Ulanib bo'lmadi: {e.__class__.__name__}"}
        ms = int((time.monotonic() - t0) * 1000)
        code = _code(r)
        if r.status_code == 401:
            return {"ok": False, "status": 401, "ms": ms, "error": "Kalit qabul qilinmadi (401): kalit noto'g'ri yoki bekor qilingan"}
        if r.status_code == 403:
            why = {"ip_not_allowed": "bu server IP'si kalitning ruxsat ro'yxatida yo'q (Yupay kabinet → Sozlamalar → IP ro'yxatini bo'shatib qo'ying)",
                   "merchant_frozen": "hisob muzlatilgan"}.get(code, code or "ruxsat yo'q")
            return {"ok": False, "status": 403, "ms": ms, "error": f"403: {why}"}
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "ms": ms, "error": f"Kutilmagan javob: {r.status_code}"}
        d = r.json()
        return {"ok": True, "status": 200, "ms": ms, "title": d.get("title"), "account": d.get("status"),
                "balance_usd": d.get("balance_usd")}

    async def balance(self) -> Decimal | None:
        try:
            r = await self.client.get("/me")
            return _dec(r.json().get("balance_usd")) if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            return None

    # ------------------------------------------------------------------ DonateProvider
    async def check_player(self, game: str, player_id: str, zone_id: str) -> str | None:
        """None — ID mavjud emas. «» — tekshirib bo'lmadi (yo'l qo'yiladi). Aks holda — nik."""
        brand = await self.brand_slug(game) if game in GAME_KEYWORD else game  # game: ML/MC yoki to'g'ridan-to'g'ri brend slug
        if not brand:
            return ""
        body = {"brand": brand, "player_id": player_id}
        if zone_id:
            body["server_id"] = zone_id
        try:
            r = await self.client.post("/validate/player", json=body)
        except httpx.HTTPError:
            return ""
        if r.status_code != 200:
            return ""
        d = r.json()
        st = d.get("status")
        if st == "invalid":
            return None
        if st == "valid":
            if d.get("reason") == "wrong_region":
                return None
            return d.get("name") or ""
        return ""  # error / unsupported — hukm yo'q

    @staticmethod
    def _fulfillment(product: dict, player_id: str, zone_id: str) -> dict:
        data: dict = {}
        for f in product.get("required_fields") or []:
            key = f.get("key")
            if not key:
                continue
            if any(w in str(key).lower() for w in ("server", "zone")):
                if zone_id:
                    data[key] = zone_id
            else:
                data[key] = player_id
        return data

    async def create(self, order_ref: str, sku: str, game: str, player_id: str, zone_id: str) -> ProviderResult:
        try:
            brands = await self.catalog()
            base, _, opt = sku.partition("@")
            found = self._find_sku(brands, base) or self._find_sku(await self.catalog(force=True), base)
        except (httpx.HTTPError, ValueError) as e:
            return ProviderResult("unknown", message=f"katalog: {e.__class__.__name__}")
        if not found:
            return ProviderResult("failed", message="unknown_sku: paketning Yupay SKU kodi katalogda yo'q (Admin → Donat paketlari)")
        product, s = found
        kind = s.get("kind") or "fixed"
        payload = {"merchant_order_id": order_ref, "sku_id": s["sku_id"], "fulfillment_data": self._fulfillment(product, player_id, zone_id)}
        if kind == "fixed":
            payload["expected_price"] = str(s.get("price_usd"))
        else:
            # erkin summa / dona: «@amt:10» yoki «@qty:100»
            what, _, val = opt.partition(":")
            unit = _dec(s.get("unit_price_usd"))
            if not val.isdigit() or unit is None or (kind, what) not in (("amount", "amt"), ("unit", "qty")):
                return ProviderResult("failed", message=f"sku_kind_not_supported: {kind}")
            if kind == "amount":
                payload["amount_usd"] = f"{int(val)}.00"
            else:
                payload["quantity"] = int(val)
            payload["expected_price"] = str((unit * int(val)).quantize(Decimal("0.01")))
        try:
            r = await self.client.post("/orders", json=payload)
        except httpx.HTTPError as e:
            return ProviderResult("unknown", message=f"network: {e.__class__.__name__}")
        return await self._after_create(r, order_ref)

    async def _after_create(self, r: httpx.Response, order_ref: str) -> ProviderResult:
        code = _code(r)
        if r.status_code in (200, 201):
            try:
                return map_order(r.json())
            except ValueError:
                return await self.status(order_ref)
        if r.status_code == 409 and code == "order_id_reused":
            return await self.status(order_ref)
        if r.status_code in (429,) or r.status_code >= 500:
            return ProviderResult("unknown", message=f"http {r.status_code}")
        hints = {
            "insufficient_deposit": "insufficient_deposit: Yupay depoziti yetmadi — depozitni to'ldiring",
            "price_changed": "price_changed: Yupay narxi o'zgargan — paket SKU/narxini yangilang",
            "margin_floor": "margin_floor: narx Yupay ruxsat etgan eng past chegaradan past",
            "invalid_credentials": "invalid_credentials: Yupay kaliti noto'g'ri",
            "ip_not_allowed": "ip_not_allowed: server IP'si Yupay ruxsat ro'yxatida yo'q",
            "merchant_frozen": "merchant_frozen: Yupay hisobi muzlatilgan",
            "item_unavailable": "item_unavailable: bu nominal hozir mavjud emas",
        }
        return ProviderResult("failed", message=hints.get(code, f"yupay {r.status_code} {code}".strip()))

    async def status(self, order_ref: str, provider_ref: str | None = None) -> ProviderResult:
        try:
            r = await self.client.get(f"/orders/{quote(order_ref, safe='')}")
        except httpx.HTTPError as e:
            return ProviderResult("unknown", message=e.__class__.__name__)
        if r.status_code == 404:
            return ProviderResult("failed", message="order_not_found")
        if r.status_code != 200:
            return ProviderResult("unknown", message=f"http {r.status_code}")
        try:
            return map_order(r.json())
        except ValueError:
            return ProviderResult("unknown", message="bad json")
