"""Yopiq rejim: ochilguncha faqat adminlar ilovadan foydalana oladi, qolganlarga «Tez kunda» chiqadi.

Hamma uchun ochish: admin botda /ochish yozadi (yopish: /yopish). Boshlang'ich holat — PUBLIC_OPEN env (standart: yopiq).
"""

import time

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

KEY = "_public_open"
COMING_SOON = "🚀 Tez kunda ochilamiz!\n\nYana biroz sabr qiling — VAYNEXO tez orada hammaga ochiladi. Yangiliklardan xabardor bo'lib turing 😉"

_cache: list = [None, 0.0]


async def text(key: str) -> str:
    """Admin paneldan tahrirlanadigan matn (Sozlamalar → Matnlar). Baza ishlamasa — standart matn."""
    from app.services import app_settings

    try:
        async with SessionLocal() as s:
            return await app_settings.get_value(s, key) or app_settings.SCHEMA[key].default
    except Exception:  # noqa: BLE001
        return app_settings.SCHEMA[key].default


async def soon_text() -> str:
    return await text("text_soon")


async def is_open() -> bool:
    if time.monotonic() - _cache[1] < 15:
        return bool(_cache[0])
    try:
        async with SessionLocal() as s:
            v = await s.scalar(select(AppSetting.value).where(AppSetting.key == KEY))
        val = settings.public_open if v is None else v == "1"
    except Exception:  # noqa: BLE001 — baza vaqtincha javob bermasa, oxirgi holat saqlanadi
        val = bool(_cache[0]) if _cache[1] else settings.public_open
    _cache[:] = [val, time.monotonic()]
    return val


async def set_open(value: bool) -> None:
    async with SessionLocal() as s, s.begin():
        await s.execute(insert(AppSetting).values(key=KEY, value="1" if value else "0")
                        .on_conflict_do_update(index_elements=["key"], set_={"value": "1" if value else "0"}))
    _cache[:] = [value, time.monotonic()]


GUESTS_KEY = "_guest_ids"  # yopiq rejimda ham kira oladigan odamlar (Telegram ID, vergul bilan)
_guests: list = [None, 0.0]


async def guests() -> set[int]:
    if time.monotonic() - _guests[1] < 15:
        return set(_guests[0] or ())
    try:
        async with SessionLocal() as s:
            v = await s.scalar(select(AppSetting.value).where(AppSetting.key == GUESTS_KEY))
        val = {int(x) for x in (v or "").split(",") if x.strip().isdigit()}
    except Exception:  # noqa: BLE001 — baza javob bermasa oxirgi ro'yxat saqlanadi
        val = set(_guests[0] or ())
    _guests[:] = [val, time.monotonic()]
    return set(val)


async def set_guests(ids: set[int]) -> None:
    v = ",".join(str(i) for i in sorted(ids))
    async with SessionLocal() as s, s.begin():
        await s.execute(insert(AppSetting).values(key=GUESTS_KEY, value=v)
                        .on_conflict_do_update(index_elements=["key"], set_={"value": v}))
    _guests[:] = [set(ids), time.monotonic()]


async def allowed(user_id: int) -> bool:
    return user_id in settings.admin_ids or await is_open() or user_id in await guests()
