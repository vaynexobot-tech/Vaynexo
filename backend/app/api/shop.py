"""O'z donat do'koningni och: do'kon yaratish, statistika, Top do'konlar."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep
from app.config import settings
from app.services import shops

router = APIRouter(prefix="/shop", tags=["shop"])


class ShopIn(BaseModel):
    slug: str = Field("", max_length=32)
    name: str = Field("", max_length=64)
    tagline: str = Field("", max_length=200)


class ShopEdit(BaseModel):
    name: str | None = Field(None, max_length=64)
    tagline: str | None = Field(None, max_length=200)


@router.get("/my")
async def my(user: CurrentUser, session: SessionDep):
    return await shops.overview(session, user, settings.bot_username)


@router.post("")
async def create(body: ShopIn, user: CurrentUser, session: SessionDep):
    async with session.begin_nested():
        await shops.create(session, user.id, body.slug, body.name, body.tagline)
    await session.commit()
    return await shops.overview(session, user, settings.bot_username)


@router.put("")
async def edit(body: ShopEdit, user: CurrentUser, session: SessionDep):
    await shops.update(session, user.id, body.name, body.tagline)
    await session.commit()
    return await shops.overview(session, user, settings.bot_username)


@router.get("/top")
async def top(user: CurrentUser, session: SessionDep, days: int = 30):
    return {"items": await shops.top(session, min(max(days, 1), 365))}
