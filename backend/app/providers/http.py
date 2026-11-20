"""Haqiqiy donat provayderi uchun HTTP adapter.

DIQQAT: provayderingiz API hujjatini bermaguningizcha bu umumiy shablon.
Kutilgan format (provayderga moslab o'zgartiring):

  POST {URL}/player/check   {"game","user_id","zone_id"}            -> {"ok":true,"nickname":"..."}
  POST {URL}/orders         {"ref","product","game","user_id","zone_id"} -> {"status":"success|pending|failed","id":"...","message":"..."}
  GET  {URL}/orders/{ref}                                           -> {"status":...,"id":...}

Sarlavha: Authorization: Bearer {DONATE_PROVIDER_KEY}
"""

import logging

import httpx

from app.providers.base import ProviderResult

log = logging.getLogger(__name__)

_MAP = {"success": "success", "done": "success", "completed": "success", "pending": "pending",
        "processing": "pending", "failed": "failed", "error": "failed", "rejected": "failed"}


class HttpProvider:
    def __init__(self, base_url: str, api_key: str, timeout: float = 20.0, cfg: dict | None = None):
        from app.config import settings as c

        cfg = cfg or {}
        self.paths = {"check": cfg.get("check_path") or c.donate_check_path, "create": cfg.get("create_path") or c.donate_create_path,
                      "status": cfg.get("status_path") or c.donate_status_path, "balance": cfg.get("balance_path") or c.donate_balance_path}
        header = cfg.get("auth_header") or c.donate_auth_header
        prefix = cfg["auth_prefix"] if "auth_prefix" in cfg else c.donate_auth_prefix
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout, headers={header: f"{prefix}{api_key}"},
        )

    async def catalog(self, force: bool = False) -> list[dict]:
        return []  # umumiy HTTP provayder katalog bermaydi: paketlar qo'lda kiritiladi

    async def ping(self) -> dict:
        """Ulanishni tekshirish: balans yo'li bo'lsa shuni, bo'lmasa o'yinchi tekshiruvini chaqiradi."""
        import time

        t0 = time.monotonic()
        try:
            if self.paths["balance"]:
                r = await self.client.get(self.paths["balance"])
            else:
                r = await self.client.post(self.paths["check"], json={"game": "ML", "user_id": "12345678", "zone_id": "1234"})
        except httpx.HTTPError as e:
            return {"ok": False, "error": f"Ulanib bo'lmadi: {e.__class__.__name__}"}
        ms = int((time.monotonic() - t0) * 1000)
        if r.status_code in (401, 403):
            return {"ok": False, "status": r.status_code, "ms": ms, "error": "Kalit qabul qilinmadi (401/403): kalit yoki sarlavha noto'g'ri"}
        if r.status_code == 404:
            return {"ok": False, "status": 404, "ms": ms, "error": "Manzil topilmadi (404): URL yoki yo'l noto'g'ri"}
        # balans javobi — kalitlar nomlarini yashirmaymiz, faqat qisqa qismini ko'rsatamiz
        return {"ok": r.status_code < 500, "status": r.status_code, "ms": ms, "sample": r.text[:200]}

    @staticmethod
    def _result(data: dict) -> ProviderResult:
        status = _MAP.get(str(data.get("status", "")).lower(), "unknown")
        return ProviderResult(status, ref=str(data.get("id") or "") or None, message=str(data.get("message") or ""))

    async def check_player(self, game: str, player_id: str, zone_id: str) -> str | None:
        try:
            r = await self.client.post(self.paths["check"], json={"game": game, "user_id": player_id, "zone_id": zone_id})
            data = r.json()
        except (httpx.HTTPError, ValueError):
            log.warning("check_player xatosi", exc_info=True)
            return None
        return data.get("nickname") if data.get("ok") else None

    async def create(self, order_ref: str, sku: str, game: str, player_id: str, zone_id: str) -> ProviderResult:
        payload = {"ref": order_ref, "product": sku, "game": game, "user_id": player_id, "zone_id": zone_id}
        try:
            r = await self.client.post(self.paths["create"], json=payload)
        except httpx.HTTPError as e:
            return ProviderResult("unknown", message=f"network: {e.__class__.__name__}")
        if r.status_code >= 500:
            return ProviderResult("unknown", message=f"http {r.status_code}")
        try:
            data = r.json()
        except ValueError:
            return ProviderResult("unknown", message=f"bad json http {r.status_code}")
        if r.status_code >= 400:
            return ProviderResult("failed", message=str(data.get("message") or f"http {r.status_code}"))
        return self._result(data)

    async def status(self, order_ref: str, provider_ref: str | None = None) -> ProviderResult:
        try:
            r = await self.client.get(self.paths["status"].format(ref=order_ref))
            if r.status_code == 404:
                return ProviderResult("failed", message="not found")
            if r.status_code >= 400:
                return ProviderResult("unknown", message=f"http {r.status_code}")
            return self._result(r.json())
        except (httpx.HTTPError, ValueError) as e:
            return ProviderResult("unknown", message=e.__class__.__name__)
