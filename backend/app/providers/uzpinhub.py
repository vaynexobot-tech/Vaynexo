"""UZPINHUB Public API (https://api.uzpinhub.uz/api/) — O'zbekistondagi B2B to'ldirish platformasi (USDT balans).

Hujjatdan asosiy qoidalar:
- Sarlavha `X-API-Key`. DIQQAT: noto'g'ri kalit bilan bir necha marta so'rov — IP butunlay bloklanadi.
  Shuning uchun 401 olinganda shu nusxa boshqa kalitli so'rov yubormaydi (ProviderAuthError), katalog cron'i API'ni o'chiradi.
- Katalog ochiq: game/topup-games (sahifali) → game/games/{id}/products, game/topup-games/{id}/required-fields;
  vaucherlar: game/simple-games → game/simple-game-products/{id} (narx, zaxira).
- Buyurtma: order/topup/buy {external_order_id, game_product_id, player_id, server_id, callback_url}
  va order/simple/buy {external_order_id, game_product_id, quantity}. Holat: processing → completed | failed.
- Buyurtma ID'si ularniki (uuid); bizning ref external_order_id da — ro'yxatdan qidirib topsa bo'ladi.
- Vaucher kodlari: user/profile/orders/{id}/values. Vebhuk: callback_url ga {order_id, status} (imzosiz — biz baribir holatni API'dan so'raymiz).
"""

import asyncio
import logging
import re
import time
from decimal import Decimal, InvalidOperation

import httpx

from app.providers.base import ProviderAuthError, ProviderResult

log = logging.getLogger(__name__)

DEFAULT_URL = "https://api.uzpinhub.uz/api"
CATALOG_TTL = 300
SLUG_PREFIX = "uz-"
SKIP_NAMES = ("telegram",)  # Telegram Premium/Stars — alohida bo'limda (TG xizmatlar)
OK_STATUS = {"completed", "complete", "success", "done", "delivered"}
FAIL_STATUS = {"failed", "fail", "error", "cancelled", "canceled", "refunded", "refund", "rejected"}
FIELD = {"userid": ("player_id", "Player ID"), "player_id": ("player_id", "Player ID"), "playerid": ("player_id", "Player ID"),
         "uid": ("player_id", "UID"), "serverid": ("server_id", "Server ID"), "server_id": ("server_id", "Server ID"),
         "zoneid": ("server_id", "Zone ID"), "zone_id": ("server_id", "Zone ID")}


def api_url(base_url: str) -> str:
    u = (base_url or "").strip().rstrip("/")
    return u if u.startswith("https://") and "uzpinhub" in u and u.endswith("/api") else DEFAULT_URL


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def _dec(v) -> Decimal | None:
    try:
        d = Decimal(str(v).replace(" ", ""))
        return d if d.is_finite() else None
    except (InvalidOperation, TypeError, ValueError):
        return None


def _msg(r: httpx.Response) -> str:
    try:
        j = r.json()
        return str(j.get("message") or j.get("detail") or j.get("error_code") or "")[:200]
    except (ValueError, AttributeError):
        return ""


def map_order(o: dict) -> ProviderResult:
    st = str(o.get("status") or "").lower()
    ref = str(o.get("order_id") or o.get("id") or "") or None
    if st in OK_STATUS:
        return ProviderResult("success", ref=ref)
    if st in FAIL_STATUS:
        return ProviderResult("failed", ref=ref, message=f"api: {st} {o.get('error_message') or ''}".strip()[:300])
    return ProviderResult("pending", ref=ref, message=st)


class UzpinhubProvider:
    manual = False
    idempotent = True

    def __init__(self, api_key: str, base_url: str = "", callback_url: str = "", timeout: float = 25.0):
        self.client = httpx.AsyncClient(base_url=api_url(base_url) + "/", timeout=timeout,
                                        headers={"X-API-Key": api_key, "Accept": "application/json"})
        self.callback_url = callback_url
        self.auth_failed = False
        self._catalog: list[dict] | None = None
        self._catalog_at = 0.0
        self._games: dict[str, str] = {}  # bizning brend slug → ularning game_id
        self._refs: dict[str, str] = {}

    # ------------------------------------------------------------------ yordamchi
    async def _get(self, path: str, auth: bool = False, **params) -> dict | list:
        if auth and self.auth_failed:
            raise ProviderAuthError("API kalit noto'g'ri — IP bloklanmasligi uchun so'rovlar to'xtatildi (kalitni yangilang)")
        for attempt in range(3):
            try:
                r = await self.client.get(path, params={k: v for k, v in params.items() if v is not None})
                break
            except httpx.TransportError:
                if attempt == 2:
                    raise
                await asyncio.sleep(1.5 * (attempt + 1))
        if r.status_code == 401:
            self.auth_failed = True
            raise ProviderAuthError("API kalit noto'g'ri (401) — IP bloklanmasligi uchun so'rovlar to'xtatildi")
        if r.status_code == 429:
            raise RuntimeError("So'rovlar juda ko'p (429)")
        r.raise_for_status()
        return r.json()

    async def _post(self, path: str, body: dict) -> httpx.Response:
        if self.auth_failed:
            raise ProviderAuthError("API kalit noto'g'ri — so'rovlar to'xtatildi")
        r = await self.client.post(path, json=body)
        if r.status_code == 401:
            self.auth_failed = True
        return r

    async def _pages(self, path: str) -> list[dict]:
        out, page = [], 1
        for _ in range(20):
            d = await self._get(path, page=page, page_size=100)
            out += d.get("data") or []
            if not d.get("next_page") or page >= int(d.get("total_pages") or 1):
                break
            page += 1
        return out

    # ------------------------------------------------------------------ katalog
    async def catalog(self, force: bool = False) -> list[dict]:
        if not force and self._catalog is not None and time.monotonic() - self._catalog_at <= CATALOG_TTL:
            return self._catalog
        topup, simple = await self._pages("game/topup-games"), await self._pages("game/simple-games")
        sem = asyncio.Semaphore(5)

        async def one_topup(g: dict) -> dict | None:
            gid, name = str(g.get("id") or ""), str(g.get("name") or "").strip()
            if not gid or not name or any(w in name.lower() for w in SKIP_NAMES):
                return None
            try:
                async with sem:
                    d = await self._get(f"game/games/{gid}/products")
                    req = await self._get(f"game/topup-games/{gid}/required-fields")
            except (httpx.HTTPError, RuntimeError) as e:
                log.warning("API o'yin o'qilmadi (%s): %s", name, e.__class__.__name__)
                return None
            fields, seen = [], set()
            for f in req if isinstance(req, list) else []:
                key, label = FIELD.get(str(f).lower().replace(" ", ""), ("player_id", str(f)))
                if key not in seen:
                    seen.add(key)
                    fields.append({"key": key, "label": label})
            skus = [{"sku_id": f"t|{p['id']}|{gid}", "name": str(p.get("name") or "").strip(), "kind": "fixed", "price_usd": str(_dec(p.get("price")))}
                    for p in (d.get("products") or []) if p.get("id") and (_dec(p.get("price")) or 0) > 0]
            if not skus:
                return None
            return {"slug": f"{SLUG_PREFIX}{slugify(name)[:50]}", "name": name[:80], "logo_url": g.get("image_url"), "category_name": "",
                    "_gid": gid, "products": [{"name": name, "required_fields": fields or [{"key": "player_id", "label": "Player ID"}], "skus": skus}]}

        async def one_simple(g: dict) -> dict | None:
            gid, name = str(g.get("id") or ""), str(g.get("name") or "").strip()
            if not gid or not name:
                return None
            try:
                async with sem:
                    d = await self._get(f"game/simple-game-products/{gid}")
            except (httpx.HTTPError, RuntimeError) as e:
                log.warning("API vaucher o'qilmadi (%s): %s", name, e.__class__.__name__)
                return None
            skus = [{"sku_id": f"v|{p['id']}", "name": str(p.get("name") or "").strip(), "kind": "fixed", "price_usd": str(_dec(p.get("price"))),
                     "stock": p.get("stock")}
                    for p in (d if isinstance(d, list) else []) if p.get("id") and (_dec(p.get("price")) or 0) > 0]
            if not skus:
                return None
            return {"slug": f"{SLUG_PREFIX}{slugify(name)[:50]}", "name": name[:80], "logo_url": g.get("image_url"), "category_name": "",
                    "products": [{"name": name, "required_fields": [], "skus": skus}]}  # maydonsiz — kod beriladi

        brands = [b for b in await asyncio.gather(*(one_topup(g) for g in topup), *(one_simple(g) for g in simple)) if b]
        seen: set[str] = set()
        for b in brands:
            base, n = b["slug"][:58], 2
            while b["slug"] in seen:
                b["slug"], n = f"{base}-{n}", n + 1
            seen.add(b["slug"])
            if b.get("_gid"):
                self._games[b["slug"]] = b.pop("_gid")
        self._catalog, self._catalog_at = brands, time.monotonic()
        return brands

    # ------------------------------------------------------------------ hisob
    async def ping(self) -> dict:
        t0 = time.monotonic()
        try:
            d = await self._get("user/profile", auth=True)
        except ProviderAuthError as e:
            return {"ok": False, "status": 401, "error": str(e)}
        except (httpx.HTTPError, RuntimeError) as e:
            return {"ok": False, "error": f"Ulanib bo'lmadi: {e.__class__.__name__} {str(e)[:120]}"}
        return {"ok": True, "status": 200, "ms": int((time.monotonic() - t0) * 1000), "title": d.get("fullname") or d.get("email"),
                "balance_usd": str(_dec(d.get("balance"))) if _dec(d.get("balance")) is not None else None}

    async def balance(self) -> Decimal | None:
        try:
            return _dec((await self._get("user/profile", auth=True)).get("balance"))
        except (httpx.HTTPError, RuntimeError, ProviderAuthError, ValueError):
            return None

    # ------------------------------------------------------------------ DonateProvider
    async def check_player(self, game: str, player_id: str, zone_id: str) -> str | None:
        """None — ID mavjud emas. «» — tekshirib bo'lmadi. Aks holda — nik."""
        gid = self._games.get(game)
        if gid is None and game.startswith(SLUG_PREFIX):
            try:
                await self.catalog()
            except (httpx.HTTPError, RuntimeError):
                return ""
            gid = self._games.get(game)
        if not gid:
            return ""
        try:
            r = await self.client.post("order/topup/check_game_ids", json={"game_id": gid, "player_id": player_id, "server_id": zone_id or ""})
        except httpx.HTTPError:
            return ""
        if r.status_code == 200:
            try:
                return str(r.json().get("gamer_name") or "")
            except ValueError:
                return ""
        return None if r.status_code in (400, 404) else ""

    async def create(self, order_ref: str, sku: str, game: str, player_id: str, zone_id: str) -> ProviderResult:
        parts = sku.split("|")
        if parts[0] == "t" and len(parts) == 3:
            body = {"external_order_id": order_ref, "game_product_id": parts[1], "player_id": player_id, "server_id": zone_id or "",
                    "callback_url": self.callback_url}
            path = "order/topup/buy"
        elif parts[0] == "v" and len(parts) == 2:
            body, path = {"external_order_id": order_ref, "game_product_id": parts[1], "quantity": 1}, "order/simple/buy"
        else:
            return ProviderResult("failed", message="unknown_sku: paket kodi noto'g'ri (katalogni yangilang)")
        try:
            r = await self._post(path, body)
        except ProviderAuthError as e:
            return ProviderResult("failed", message=str(e))
        except httpx.HTTPError as e:
            return ProviderResult("unknown", message=f"network: {e.__class__.__name__}")
        if r.status_code in (200, 201):
            try:
                res = map_order(r.json())
            except ValueError:
                return ProviderResult("unknown", message="bad json")
            if res.ref:
                self._refs[order_ref] = res.ref
            return await self._with_codes(res) if parts[0] == "v" else res
        if r.status_code == 429 or r.status_code >= 500:
            return ProviderResult("unknown", message=f"http {r.status_code}")
        if r.status_code == 401:
            return ProviderResult("failed", message="API kalit noto'g'ri (401)")
        return ProviderResult("failed", message=f"api {r.status_code}: {_msg(r)}".strip()[:300])

    async def _find_ref(self, order_ref: str) -> str | None:
        """Bizning ref (external_order_id) bo'yicha ularning buyurtma ID'si — oxirgi buyurtmalar ro'yxatidan."""
        for page in (1, 2, 3):
            d = await self._get("user/profile/orders", auth=True, page=page, page_size=50)
            for o in d.get("data") or []:
                if str(o.get("external_order_id")) == order_ref:
                    return str(o.get("id"))
            if not d.get("next_page"):
                break
        return None

    async def _with_codes(self, res: ProviderResult) -> ProviderResult:
        if res.status != "success" or not res.ref:
            return res
        try:
            vals = await self._get(f"user/profile/orders/{res.ref}/values", auth=True)
        except (httpx.HTTPError, RuntimeError, ProviderAuthError):
            return res  # kod keyingi holat so'rovida olinadi
        codes = [str(v) for v in vals if v] if isinstance(vals, list) else []
        return ProviderResult("success", ref=res.ref, artifact={"code": "\n".join(codes)[:500]}) if codes else res

    async def status(self, order_ref: str, provider_ref: str | None = None) -> ProviderResult:
        try:
            ref = provider_ref or self._refs.get(order_ref) or await self._find_ref(order_ref)
            if not ref:
                return ProviderResult("unknown", message="buyurtma topilmadi")  # «failed» emas — pul qaytarilib ketmasin
            o = await self._get(f"user/profile/orders/{ref}", auth=True)
        except ProviderAuthError as e:
            return ProviderResult("unknown", message=str(e))
        except (httpx.HTTPError, RuntimeError, ValueError) as e:
            return ProviderResult("unknown", message=e.__class__.__name__)
        res = map_order({**o, "order_id": o.get("id") or ref})
        return await self._with_codes(res)
