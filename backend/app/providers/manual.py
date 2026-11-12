"""Qo'lda bajarish: API ulanmaguncha har bir donat buyurtmasi admin guruhiga («buyurtma» mavzusi) tushadi.

Admin almazni o'zi tashlaydi (Codashop, Smile.One va h.k.) va «✅ Bajarildi» yoki «↩️ Pulni qaytarish» ni bosadi.
"""

from app.providers.base import ProviderResult


class ManualProvider:
    manual = True

    async def check_player(self, game: str, player_id: str, zone_id: str) -> str | None:
        return "qo'lda tekshiriladi" if player_id.isdigit() and len(player_id) >= 5 else None

    async def create(self, order_ref: str, sku: str, game: str, player_id: str, zone_id: str) -> ProviderResult:
        return ProviderResult("manual")

    async def status(self, order_ref: str) -> ProviderResult:
        return ProviderResult("manual")
