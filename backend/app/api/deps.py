import logging
import time
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.errors import AppError, Forbidden
from app.models import User
from app.security import validate_init_data

log = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis
    if not settings.redis_url:
        raise RuntimeError("Redis sozlanmagan (yengil rejim)")
    if _redis is None:
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


_mem_counts: dict[str, int] = {}


def _mem_incr(k: str) -> int:
    """Yengil rejim: jarayon xotirasidagi hisoblagich (eski oynalar tozalanadi)."""
    if len(_mem_counts) > 50_000:
        _mem_counts.clear()
    _mem_counts[k] = _mem_counts.get(k, 0) + 1
    return _mem_counts[k]


async def rate_limit(key: str, limit: int, window: int) -> None:
    """Oddiy oyna bo'yicha cheklov. Redis ishlamasa — o'tkazib yuboradi."""
    if not settings.redis_url:
        if _mem_incr(f"rl:{key}:{int(time.time()) // window}") > limit:
            raise AppError("rate_limited", "Juda ko'p so'rov. Birozdan so'ng urinib ko'ring", 429)
        return
    try:
        r = get_redis()
        k = f"rl:{key}:{int(time.time()) // window}"
        n = await r.incr(k)
        if n == 1:
            await r.expire(k, window)
    except Exception:
        log.debug("rate limit o'tkazib yuborildi", exc_info=True)
        return
    if n > limit:
        raise AppError("rate_limited", "Juda ko'p so'rov. Birozdan so'ng urinib ko'ring", 429)


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _parse_ref(start_param: str | None, user_id: int) -> int | None:
    if start_param and start_param.startswith("ref_"):
        try:
            ref = int(start_param[4:])
        except ValueError:
            return None
        return ref if ref != user_id else None
    return None


async def current_user(
    request: Request,
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
    x_dev_user: Annotated[str | None, Header()] = None,
) -> User:
    tg: dict | None = None
    if authorization and authorization.startswith("tma "):
        tg = validate_init_data(authorization[4:], settings.bot_token)
    elif settings.dev_mode and x_dev_user:
        tg = {"id": int(x_dev_user), "first_name": f"Dev {x_dev_user}", "username": f"dev{x_dev_user}"}
    if tg is None:
        raise AppError("unauthorized", "Ilovani Telegram orqali oching", 401)

    uid = int(tg["id"])
    if request.method != "GET":
        await rate_limit(f"u:{uid}", limit=30, window=10)

    user = await session.get(User, uid)
    if user is None:
        ref = _parse_ref(tg.get("start_param"), uid)
        if ref and not await session.get(User, ref):
            ref = None
        user = User(
            id=uid,
            username=tg.get("username"),
            first_name=(tg.get("first_name") or "")[:128],
            lang="ru" if (tg.get("language_code") or "").startswith("ru") else "uz",
            referrer_id=ref,
            is_admin=uid in settings.admin_ids,
        )
        session.add(user)
        await session.commit()
    else:
        if tg.get("username") != user.username:
            user.username = tg.get("username")
        if uid in settings.admin_ids and not user.is_admin:
            user.is_admin = True
        # Tranzaksiyani yopamiz (rollback obyektlarni eskirtiradi, commit esa yo'q) — endpoint o'zinikini ochadi.
        await session.commit()
    if user.is_banned:
        raise Forbidden("Hisobingiz bloklangan. Yordam: @vaynexo_support")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def admin_user(user: CurrentUser) -> User:
    if not (user.is_admin or user.id in settings.admin_ids):
        raise Forbidden()
    return user


AdminUser = Annotated[User, Depends(admin_user)]


def page_params(limit: int = 20, offset: int = 0) -> tuple[int, int]:
    return max(1, min(limit, 50)), max(0, offset)


async def get_or_none(session: AsyncSession, model, **where):
    return await session.scalar(select(model).filter_by(**where))
