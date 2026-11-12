from dataclasses import dataclass
from typing import Literal, Protocol

Status = Literal["success", "pending", "failed", "unknown", "manual"]


@dataclass
class ProviderResult:
    """success — almaz tushdi; pending — provayder hali bajaryapti;
    failed — aniq rad etildi (pul qaytariladi);
    unknown — javob olinmadi (timeout/5xx): almaz tushgan-tushmagani noma'lum.
    """

    status: Status
    ref: str | None = None
    message: str = ""


class DonateProvider(Protocol):
    async def check_player(self, game: str, player_id: str, zone_id: str) -> str | None:
        """O'yinchi nikini qaytaradi; topilmasa None."""

    async def create(self, order_ref: str, sku: str, game: str, player_id: str, zone_id: str) -> ProviderResult:
        """Buyurtma berish. `order_ref` bizning noyob ID — provayder uni takrorni oldini olish uchun ishlatishi kerak."""

    async def status(self, order_ref: str) -> ProviderResult:
        """Avval berilgan buyurtma holati."""
