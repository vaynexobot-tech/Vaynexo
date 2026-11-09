"""Sinov provayderi: haqiqiy almaz yubormaydi.

* player_id "0" bilan boshlansa — rad etadi (pul qaytishini sinash uchun);
* player_id "9" bilan boshlansa — javob bermaydi (unknown holatini sinash uchun);
* qolganlari — muvaffaqiyatli.
"""

from app.providers.base import ProviderResult


class MockProvider:
    async def check_player(self, game: str, player_id: str, zone_id: str) -> str | None:
        if not player_id.isdigit() or len(player_id) < 5:
            return None
        return f"Player_{player_id[-4:]}"

    async def create(self, order_ref: str, sku: str, game: str, player_id: str, zone_id: str) -> ProviderResult:
        if player_id.startswith("0"):
            return ProviderResult("failed", message="Player not found")
        if player_id.startswith("9"):
            return ProviderResult("unknown", message="timeout")
        return ProviderResult("success", ref=f"MOCK-{order_ref}")

    async def status(self, order_ref: str) -> ProviderResult:
        return ProviderResult("success", ref=f"MOCK-{order_ref}")
