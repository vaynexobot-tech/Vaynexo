"""Yopiq rejim: ochilguncha faqat adminlar ilovadan foydalana oladi, qolganlarga «Tez kunda» chiqadi.

Hamma uchun ochish: admin botda /ochish yozadi (yopish: /yopish). Boshlang'ich holat — PUBLIC_OPEN env (standart: yopiq).
"""

import time

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db import SessionLocal
from app.models import AppSetting

KEY = "_public_open"
COMING_SOON = "🚀 Tez kunda ochilamiz!\n\nYana biroz sabr qiling — VAYNEXO tez orada hammaga ochiladi. Yangiliklardan xabardor bo'lib turing 😉"

_cache: list = [None, 0.0]


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


async def allowed(user_id: int) -> bool:
    return user_id in settings.admin_ids or await is_open()
