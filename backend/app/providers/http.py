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
    def __init__(self, base_url: str, api_key: str, timeout: float = 20.0):
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), timeout=timeout, headers={"Authorization": f"Bearer {api_key}"}
        )

    @staticmethod
    def _result(data: dict) -> ProviderResult:
        status = _MAP.get(str(data.get("status", "")).lower(), "unknown")
        return ProviderResult(status, ref=str(data.get("id") or "") or None, message=str(data.get("message") or ""))

    async def check_player(self, game: str, player_id: str, zone_id: str) -> str | None:
        try:
            r = await self.client.post("/player/check", json={"game": game, "user_id": player_id, "zone_id": zone_id})
            data = r.json()
        except (httpx.HTTPError, ValueError):
            log.warning("check_player xatosi", exc_info=True)
            return None
        return data.get("nickname") if data.get("ok") else None

    async def create(self, order_ref: str, sku: str, game: str, player_id: str, zone_id: str) -> ProviderResult:
        payload = {"ref": order_ref, "product": sku, "game": game, "user_id": player_id, "zone_id": zone_id}
        try:
            r = await self.client.post("/orders", json=payload)
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

    async def status(self, order_ref: str) -> ProviderResult:
        try:
            r = await self.client.get(f"/orders/{order_ref}")
            if r.status_code == 404:
                return ProviderResult("failed", message="not found")
            if r.status_code >= 400:
                return ProviderResult("unknown", message=f"http {r.status_code}")
            return self._result(r.json())
        except (httpx.HTTPError, ValueError) as e:
            return ProviderResult("unknown", message=e.__class__.__name__)
