"""Admin paneldan o'zgartiriladigan sozlamalar (bazada saqlanadi).

Qiymat bazada bo'lmasa — config (.env) dagi boshlang'ich qiymat ishlatiladi.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError
from app.models import AppSetting

# kalit: (turi, boshlang'ich qiymat, min, max, izoh)
SCHEMA: dict[str, tuple[type, object, int, int, str]] = {
    "referral_bonus": (int, None, 0, 10_000_000, "Taklif bonusi (so'm): do'st birinchi marta to'ldirganda. 0 — o'chiq"),
    "referral_min_topup": (int, 10_000, 1_000, 100_000_000, "Bonus uchun do'stning eng kam to'ldirishi (so'm)"),
}


def _default(key: str):
    typ, default, *_ = SCHEMA[key]
    return default if default is not None else getattr(settings, key)


async def get_value(session: AsyncSession, key: str):
    typ = SCHEMA[key][0]
    raw = await session.scalar(select(AppSetting.value).where(AppSetting.key == key))
    if raw is None:
        return _default(key)
    try:
        return typ(raw)
    except ValueError:
        return _default(key)


async def get_all(session: AsyncSession) -> list[dict]:
    return [
        {"key": k, "value": await get_value(session, k), "min": lo, "max": hi, "label": label}
        for k, (_, _, lo, hi, label) in SCHEMA.items()
    ]


async def set_value(session: AsyncSession, key: str, value) -> None:
    if key not in SCHEMA:
        raise AppError("bad_setting", "Noma'lum sozlama")
    typ, _, lo, hi, _ = SCHEMA[key]
    try:
        value = typ(value)
    except (TypeError, ValueError) as e:
        raise AppError("bad_setting", "Qiymat noto'g'ri") from e
    if not lo <= value <= hi:
        raise AppError("bad_setting", f"Qiymat {lo} dan {hi} gacha bo'lishi kerak")
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=str(value)))
    else:
        row.value = str(value)
