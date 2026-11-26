"""O'z donat do'koningni och: do'kon yaratish, statistika, Top do'konlar."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep, rate_limit
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


@router.post("/card")
async def send_card(user: CurrentUser, session: SessionDep):
    """Reklama rasmini (QR bilan) botdan egasining o'ziga yuboradi — kanalga yoki hikoyaga qo'yish uchun."""
    from aiogram.types import BufferedInputFile

    from app.bot.instance import get_bot
    from app.errors import BadState, NotFound
    from app.models import Shop
    from sqlalchemy import select

    await rate_limit(f"shopcard:{user.id}", limit=5, window=600)
    shop = await session.scalar(select(Shop).where(Shop.owner_id == user.id))
    if shop is None:
        raise NotFound("Do'kon")
    if not settings.bot_username:
        raise BadState("Bot manzili sozlanmagan")
    link = shops.shop_link(settings.bot_username, shop.slug)
    png = shops.promo_card_png(shop.name, shop.tagline, link)
    await get_bot().send_photo(user.id, BufferedInputFile(png, "do'kon.png"),
                               caption=f"🏪 {shop.name}\n\nBu rasmni kanalingizga qo'ying: skaner qilgan har bir odam sizning mijozingiz bo'ladi.\n{link}")
    return {"ok": True}


@router.get("/top")
async def top(user: CurrentUser, session: SessionDep, days: int = 30):
    return {"items": await shops.top(session, min(max(days, 1), 365))}
