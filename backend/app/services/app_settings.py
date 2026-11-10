"""Admin paneldan o'zgartiriladigan sozlamalar (bazada saqlanadi).

Qiymat bazada bo'lmasa — boshlang'ich qiymat (yoki config/.env dagisi) ishlatiladi.
Turlari: money (so'm), percent (%), choice (ro'yxatdan bittasi).
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError
from app.models import AppSetting


@dataclass(frozen=True)
class Spec:
    kind: str  # money | percent | choice
    default: object  # None -> config dagi shu nomli qiymat
    label: str
    group: str
    lo: int = 0
    hi: int = 100_000_000
    choices: dict[str, str] = field(default_factory=dict)


SCHEMA: dict[str, Spec] = {
    # Referal
    "referral_bonus": Spec("money", None, "Taklif bonusi (so'm). 0 — o'chiq", "Referal", 0, 10_000_000),
    "referral_min_topup": Spec("money", 10_000, "Bonus uchun do'stning eng kam to'ldirishi (so'm)", "Referal", 1_000),
    # Savdo
    "vip_price_per_day": Spec("money", 5_000, "VIP e'lon narxi (so'm / kun)", "Account savdo", 0, 10_000_000),
    # Ijara
    "rent_deposit_type": Spec("choice", "percent", "Ijara depoziti turi", "Account ijara",
                              choices={"percent": "Ijara narxidan foiz", "fixed": "Aniq summa"}),
    "rent_deposit_percent": Spec("percent", 100, "Depozit: ijara narxining necha foizi (%)", "Account ijara", 0, 1000),
    "rent_deposit_fixed": Spec("money", 50_000, "Depozit: aniq summa (so'm)", "Account ijara", 0, 100_000_000),
    "rent_commission_percent": Spec("percent", 10, "Ijaradan platforma ulushi (%)", "Account ijara", 0, 90),
    # Boost
    "boost_express_percent": Spec("percent", 30, "Express boost ustamasi (%)", "Boost", 0, 500),
    "boost_hero_percent": Spec("percent", 15, "Qahramon tanlash ustamasi (%)", "Boost", 0, 500),
    "boost_lane_percent": Spec("percent", 10, "Liniya tanlash ustamasi (%)", "Boost", 0, 500),
}


def _default(key: str):
    spec = SCHEMA[key]
    return spec.default if spec.default is not None else getattr(settings, key)


def _parse(spec: Spec, raw):
    if spec.kind == "choice":
        value = str(raw)
        if value not in spec.choices:
            raise ValueError(value)
        return value
    return int(raw)


async def get_value(session: AsyncSession, key: str):
    raw = await session.scalar(select(AppSetting.value).where(AppSetting.key == key))
    if raw is None:
        return _default(key)
    try:
        return _parse(SCHEMA[key], raw)
    except (TypeError, ValueError):
        return _default(key)


async def get_many(session: AsyncSession, *keys: str) -> dict:
    return {k: await get_value(session, k) for k in keys}


async def get_all(session: AsyncSession) -> list[dict]:
    return [
        {"key": k, "value": await get_value(session, k), "kind": s.kind, "min": s.lo, "max": s.hi, "label": s.label,
         "group": s.group, "choices": [{"v": v, "label": lbl} for v, lbl in s.choices.items()]}
        for k, s in SCHEMA.items()
    ]


async def set_value(session: AsyncSession, key: str, value) -> None:
    spec = SCHEMA.get(key)
    if spec is None:
        raise AppError("bad_setting", "Noma'lum sozlama")
    try:
        value = _parse(spec, value)
    except (TypeError, ValueError) as e:
        raise AppError("bad_setting", "Qiymat noto'g'ri") from e
    if spec.kind != "choice" and not spec.lo <= value <= spec.hi:
        raise AppError("bad_setting", f"Qiymat {spec.lo} dan {spec.hi} gacha bo'lishi kerak")
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=str(value)))
    else:
        row.value = str(value)
