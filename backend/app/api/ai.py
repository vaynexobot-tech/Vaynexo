"""AI bo'limi: savol-javob va e'lonni AI bilan to'ldirish. Kunlik cheklov bilan."""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api import deps
from app.api import schemas as S
from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.config import settings
from app.errors import AppError
from app.services import ai

log = logging.getLogger(__name__)
router = APIRouter(tags=["ai"])


def _key(uid: int) -> str:
    return f"ai:{uid}:{datetime.now(timezone.utc):%Y%m%d}"


async def _used(uid: int) -> int:
    if not settings.redis_url:
        return deps._mem_counts.get(_key(uid), 0)
    try:
        return int(await deps.get_redis().get(_key(uid)) or 0)
    except Exception:
        return 0


async def _spend(uid: int) -> None:
    if not settings.redis_url:
        deps._mem_incr(_key(uid))
        return
    try:
        r = deps.get_redis()
        if await r.incr(_key(uid)) == 1:
            await r.expire(_key(uid), 26 * 3600)
    except Exception:
        log.debug("AI hisoblagichi yozilmadi", exc_info=True)


async def _check_left(uid: int) -> int:
    left = settings.ai_daily_limit - await _used(uid)
    if left <= 0:
        raise AppError("ai_limit", "Bugungi AI so'rovlar tugadi. Ertaga yana yozing", 429)
    return left


@router.get("/ai/status")
async def status(user: CurrentUser):
    return {"enabled": bool(settings.anthropic_api_key), "limit": settings.ai_daily_limit,
            "left": max(0, settings.ai_daily_limit - await _used(user.id))}


class HistoryItem(BaseModel):
    role: str = Field(pattern="^(user|ai)$")
    text: str = Field(max_length=2000)


class AskIn(BaseModel):
    text: str = Field(min_length=2, max_length=500)
    history: list[HistoryItem] = Field(default_factory=list, max_length=12)


@router.post("/ai/ask")
async def ask(body: AskIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"aiq:{user.id}", limit=5, window=60)
    left = await _check_left(user.id)
    reply, items = await ai.ask(session, user.lang, body.text.strip(), [h.model_dump() for h in body.history])
    await _spend(user.id)
    return {"reply": reply, "listings": [S.listing_card(x) for x in items], "left": left - 1}


class DescribeIn(BaseModel):
    game: str = Field(max_length=8)
    rank: str = Field("", max_length=32)
    server: str = Field("", max_length=32)
    collection_level: str = Field("", max_length=32)
    skins: int = Field(0, ge=0, le=5000)
    heroes: int = Field(0, ge=0, le=500)
    notes: str = Field("", max_length=500)


@router.post("/ai/describe")
async def describe(body: DescribeIn, user: CurrentUser):
    await rate_limit(f"aiq:{user.id}", limit=5, window=60)
    left = await _check_left(user.id)
    fields = body.model_dump(exclude={"notes"})
    fields["game"] = "Mobile Legends" if body.game == "ML" else "Magic Chess"
    out = await ai.describe_listing(user.lang, fields, body.notes.strip())
    await _spend(user.id)
    return {**out, "left": left - 1}
