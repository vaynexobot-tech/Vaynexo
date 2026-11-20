"""FazerCards Reseller API v2 (https://reseller.fazercards.com/en/docs) — donat (to'g'ridan-to'g'ri ID bilan to'ldirish).

Asosiy qoidalar (hujjatdan):
- Bazaviy manzil https://api.fzr.cards/api/v2 ; sarlavha `X-API-Key: <kalit>`. Hisob USD'da, oldindan to'lov (kripto bilan to'ldiriladi).
- Katalog ikki bosqichli: GET /topups (kategoriyalar, kursor) → GET /topups/offers?category_id=… (paketlar + maydonlar).
- Buyurtma: POST /topups/order {category_id, offer_id, fields}; `Idempotency-Key` sarlavhasi takroriy yuborishni xavfsiz qiladi
  (biz unga o'z buyurtma ID'mizni beramiz: VX-D123). 7 kun saqlanadi.
- Buyurtma ID'si ularniki (`ord-123`): bizniki emas. Shuning uchun holat so'rovi uchun `provider_ref` (ularning ID'si) kerak.
- Holat: processing → completed | failed | refund.
- Vebhuk tanasida kod yo'q; imzo `X-Webhook-Signature: sha256=<HMAC-SHA256(tana, vebhuk siri)>`.
"""

import asyncio
import logging
import re
import time
from decimal import Decimal, InvalidOperation

import httpx

from app.providers.base import ProviderResult

log = logging.getLogger(__name__)

DEFAULT_URL = "https://api.fzr.cards/api/v2"
CATALOG_TTL = 300
SEP = "|"  # provider_sku = «<category_id>|<offer_id>» (juftlik noyob; offer_id turli kategoriyada takrorlanishi mumkin)
SLUG_PREFIX = "fz-"  # Yupay o'yinlari bilan aralashmaslik uchun alohida nom maydoni

OK_STATUS = {"completed", "complete", "done", "success", "delivered"}
FAIL_STATUS = {"failed", "refund", "refunded", "cancelled", "canceled", "rejected", "error"}


def api_url(base_url: str) -> str:
    """Faqat API v2 manzili qabul qilinadi; sayt/kabinet manzili kiritilsa — standart manzil."""
    u = (base_url or "").strip().rstrip("/")
    return u if u.startswith("https://") and "/api/" in u + "/" else DEFAULT_URL


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def _dec(v) -> Decimal | None:
    try:
        d = Decimal(str(v))
        return d if d.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _err(r: httpx.Response) -> tuple[str, str]:
    """(mashina kodi, odam o'qiydigan xabar) — javob tanasidan."""
    try:
        j = r.json()
        return str(j.get("code") or ""), str(j.get("error") or j.get("message") or "")
    except (ValueError, AttributeError):
        return "", ""


def map_order(order: dict) -> ProviderResult:
    """FazerCards buyurtma obyektini bizning natijaga aylantirish."""
    status = str(order.get("status") or "").lower()
    ref = str(order.get("id") or order.get("order_id") or "") or None
    if status in OK_STATUS:
        return ProviderResult("success", ref=ref, artifact=_artifact(order))
    if status in FAIL_STATUS:
        return ProviderResult("failed", ref=ref, message=f"fazercards: {status}")
    return ProviderResult("pending", ref=ref, message=status)  # processing va yangi noma'lum holatlar — hali jarayonda


def _artifact(order: dict) -> dict | None:
    """Kod beriladigan buyurtmalar (`cards`) — to'g'ridan-to'g'ri ID bilan to'ldirishda bo'lmaydi, lekin zarar qilmaydi."""
    cards = order.get("cards")
    if not isinstance(cards, list) or not cards:
        return None
    c = cards[0]
    if isinstance(c, str):
        return {"code": c[:500]}
    if isinstance(c, dict):
        out = {k: str(c[k])[:500] for k in ("code", "pin", "serial", "link") if c.get(k) not in (None, "")}
        return out or None
    return None


class FazerCardsProvider:
    manual = False
    idempotent = True  # topups/order Idempotency-Key bilan takrorlash xavfsiz

    def __init__(self, api_key: str, base_url: str = "", timeout: float = 25.0):
        self.client = httpx.AsyncClient(
            base_url=api_url(base_url), timeout=timeout,
            headers={"X-API-Key": api_key, "Accept": "application/json"},
        )
        self._catalog: list[dict] | None = None
        self._catalog_at = 0.0
        self._offers: dict[str, tuple[float, dict]] = {}
        self._refs: dict[str, str] = {}  # bizning ref → ularning buyurtma ID'si (DB'dagi provider_ref zaxira)
        self._validate: tuple[float, list[dict]] | None = None

    # ------------------------------------------------------------------ yordamchi
    async def _get(self, path: str, **params) -> dict:
        r = await self.client.get(path, params={k: v for k, v in params.items() if v is not None})
        if r.status_code in (401, 403):
            code, msg = _err(r)
            if code == "subscription_inactive":
                raise RuntimeError("FazerCards obunasi faol emas (kabinetda rejani yoqing yoki sinovni boshlang)")
            raise RuntimeError("API kalit noto'g'ri, bekor qilingan yoki bu hisobga ruxsat yo'q" + (f" ({msg})" if msg else ""))
        if r.status_code == 429:
            raise RuntimeError("So'rovlar juda ko'p (429) — birozdan keyin urinib ko'ring")
        r.raise_for_status()
        try:
            return r.json()
        except ValueError:
            raise RuntimeError(f"FazerCards JSON o'rniga sahifa qaytardi ({r.status_code})") from None

    async def _category_list(self) -> list[dict]:
        items: list[dict] = []
        cursor = None
        for _ in range(20):  # himoya: cheksiz sahifalashdan
            d = await self._get("/topups", limit=500, cursor=cursor, include_ui=1)
            items += d.get("items") or []
            meta = d.get("meta") or {}
            cursor = meta.get("next_cursor")
            if not meta.get("has_more") or not cursor:
                break
        return items

    async def _category_offers(self, category_id: str, force: bool = False) -> dict:
        hit = self._offers.get(category_id)
        if hit and not force and time.monotonic() - hit[0] < CATALOG_TTL:
            return hit[1]
        d = await self._get("/topups/offers", category_id=category_id, include_ui=1)
        self._offers[category_id] = (time.monotonic(), d)
        return d

    # ------------------------------------------------------------------ katalog (Yupay formatiga o'xshash: sync_provider shuni kutadi)
    async def catalog(self, force: bool = False) -> list[dict]:
        if not force and self._catalog is not None and time.monotonic() - self._catalog_at <= CATALOG_TTL:
            return self._catalog
        cats = await self._category_list()
        sem = asyncio.Semaphore(4)  # katalog o'qish chegarasi: 120/daqiqa

        async def one(c: dict) -> dict | None:
            cid = str(c.get("category_id") or "")
            if not cid:
                return None
            try:
                async with sem:
                    d = await self._category_offers(cid, force=True)
            except (httpx.HTTPError, RuntimeError) as e:
                log.warning("FazerCards kategoriya o'qilmadi (%s): %s", cid, e.__class__.__name__)
                return None
            skus = []
            for o in d.get("offers") or []:
                oid, price = o.get("offer_id"), _dec(o.get("price_usd"))
                if not oid or price is None or price <= 0:
                    continue
                skus.append({"sku_id": f"{cid}{SEP}{oid}", "name": str(o.get("name") or ""), "kind": "fixed", "price_usd": str(price)})
            if not skus:
                return None
            fields = [{"key": f.get("key"), "label": f.get("label") or f.get("key"), "placeholder": "", "pattern": ""}
                      for f in d.get("fields") or [] if f.get("key")]
            name = str(d.get("name") or c.get("name") or cid)[:80]  # DonateGame.name — 80 belgi
            return {"slug": f"{SLUG_PREFIX}{(slugify(name) or slugify(cid))[:50]}", "name": name, "logo_url": c.get("imageurl") or d.get("imageurl"),
                    "category_name": "FazerCards",
                    "products": [{"name": name, "required_fields": fields or [{"key": "player_id", "label": "Player ID"}], "skus": skus}]}

        brands = [b for b in await asyncio.gather(*(one(c) for c in cats)) if b]
        seen: set[str] = set()
        for b in brands:  # bir xil nomli kategoriyalar (mintaqalar) to'qnashmasin
            base, n = b["slug"][:58], 2  # DonateGame.slug — 64 belgi
            while b["slug"] in seen:
                b["slug"], n = f"{base}-{n}", n + 1
            seen.add(b["slug"])
        self._catalog, self._catalog_at = brands, time.monotonic()
        return brands

    # ------------------------------------------------------------------ hisob
    async def ping(self) -> dict:
        t0 = time.monotonic()
        try:
            r = await self.client.get("/me")
        except httpx.HTTPError as e:
            return {"ok": False, "error": f"Ulanib bo'lmadi: {e.__class__.__name__}"}
        ms = int((time.monotonic() - t0) * 1000)
        if r.status_code == 401:
            return {"ok": False, "status": 401, "ms": ms, "error": "Kalit qabul qilinmadi (401): kalit noto'g'ri yoki bekor qilingan"}
        if r.status_code == 403:
            code, _ = _err(r)
            why = "obuna faol emas (kabinetda sinov yoki reja yoqing)" if code == "subscription_inactive" else (code or "ruxsat yo'q yoki hisob bloklangan")
            return {"ok": False, "status": 403, "ms": ms, "error": f"403: {why}"}
        if r.status_code != 200:
            return {"ok": False, "status": r.status_code, "ms": ms, "error": f"Kutilmagan javob: {r.status_code}"}
        d = r.json()
        bal = await self.balance()
        if d.get("subscriptionActive") is False:
            return {"ok": False, "status": 200, "ms": ms, "error": "Obuna faol emas — buyurtmalar rad etiladi (kabinetda reja yoqing)",
                    "balance_usd": str(bal) if bal is not None else None}
        return {"ok": True, "status": 200, "ms": ms, "title": d.get("login"), "account": d.get("plan"),
                "balance_usd": str(bal) if bal is not None else None}

    async def balance(self) -> Decimal | None:
        try:
            r = await self.client.get("/balance")
            return _dec(r.json().get("balance")) if r.status_code == 200 else None
        except (httpx.HTTPError, ValueError):
            return None

    # ------------------------------------------------------------------ DonateProvider
    async def check_player(self, game: str, player_id: str, zone_id: str) -> str | None:
        """None — ID mavjud emas. «» — tekshirib bo'lmadi (yo'l qo'yiladi). Aks holda — nik."""
        want = game[len(SLUG_PREFIX):] if game.startswith(SLUG_PREFIX) else None
        if not want:
            return ""
        try:
            if self._validate is None or time.monotonic() - self._validate[0] > CATALOG_TTL:
                r = await self.client.get("/topups/validate-id")
                self._validate = (time.monotonic(), r.json().get("items") or [] if r.status_code == 200 else [])
            item = next((x for x in self._validate[1] if slugify(x.get("name", "")) == want or x.get("category_id") == want), None)
            if not item:
                return ""
            body = {"category_id": item["category_id"], "fields": self._fill(item.get("fields") or [], player_id, zone_id)}
            r = await self.client.post("/topups/validate-id", json=body)
        except (httpx.HTTPError, ValueError, KeyError):
            return ""
        if r.status_code != 200:
            return ""
        try:
            d = r.json()
        except ValueError:
            return ""
        if d.get("valid") is False:
            return None
        return str(d.get("player_name") or "") if d.get("valid") else ""

    @staticmethod
    def _fill(fields: list[dict], player_id: str, zone_id: str) -> dict:
        """Bizning player_id/zone_id ni kategoriya maydonlariga joylash (server/zona — ikkinchisi)."""
        out: dict = {}
        for f in fields:
            key = f.get("key")
            if not key:
                continue
            if any(w in str(key).lower() for w in ("server", "zone", "region")):
                if zone_id:
                    out[key] = zone_id
            else:
                out[key] = player_id
        return out

    async def create(self, order_ref: str, sku: str, game: str, player_id: str, zone_id: str) -> ProviderResult:
        cid, _, oid = sku.partition(SEP)
        if not cid or not oid:
            return ProviderResult("failed", message="unknown_sku: paket kodi noto'g'ri (Admin → Donat paketlari)")
        try:
            d = await self._category_offers(cid)
        except (httpx.HTTPError, RuntimeError) as e:
            return ProviderResult("unknown", message=f"katalog: {e.__class__.__name__}")
        if not any(str(o.get("offer_id")) == oid for o in d.get("offers") or []):
            return ProviderResult("failed", message="unknown_sku: paket FazerCards katalogida yo'q (katalogni yangilang)")
        payload = {"category_id": cid, "offer_id": oid, "fields": self._fill(d.get("fields") or [], player_id, zone_id)}
        try:
            r = await self.client.post("/topups/order", json=payload, headers={"Idempotency-Key": order_ref})
        except httpx.HTTPError as e:
            return ProviderResult("unknown", message=f"network: {e.__class__.__name__}")
        res = self._after_create(r)
        if res.ref:
            self._refs[order_ref] = res.ref
        return res

    @staticmethod
    def _after_create(r: httpx.Response) -> ProviderResult:
        if r.status_code in (200, 201):
            try:
                order = r.json().get("order") or {}
            except ValueError:
                return ProviderResult("unknown", message="bad json")
            return map_order(order)
        if r.status_code == 429 or r.status_code >= 500 or r.status_code == 409:
            return ProviderResult("unknown", message=f"http {r.status_code}")
        code, msg = _err(r)
        hints = {
            "subscription_inactive": "subscription_inactive: FazerCards obunasi faol emas",
            "insufficient_balance": "insufficient_balance: FazerCards balansi yetmadi — balansni to'ldiring",
        }
        if r.status_code in (401, 403):
            return ProviderResult("failed", message=hints.get(code, f"fazercards {r.status_code}: kalit/ruxsat xatosi {code}".strip()))
        return ProviderResult("failed", message=hints.get(code, f"fazercards {r.status_code} {code} {msg}".strip())[:300])

    async def status(self, order_ref: str, provider_ref: str | None = None) -> ProviderResult:
        ref = provider_ref or self._refs.get(order_ref)
        if not ref:
            return ProviderResult("unknown", message="buyurtma ID'si noma'lum")  # hech qachon «failed» emas: pul qaytarilib ketmasin
        try:
            r = await self.client.get(f"/orders/{ref}")
        except httpx.HTTPError as e:
            return ProviderResult("unknown", message=e.__class__.__name__)
        if r.status_code != 200:
            return ProviderResult("unknown", message=f"http {r.status_code}")
        try:
            return map_order(r.json().get("order") or {})
        except ValueError:
            return ProviderResult("unknown", message="bad json")
