"""Birgalikda to'laymiz / Orzu ro'yxati, Draft Jang, kunlik seriya, Meta bashorat, o'yinchi kartasi."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.config import settings
from app.errors import BadState
from app.queue import enqueue
from app.services import arena, card, duel, habit, split
from app.services.notify import Outbox

router = APIRouter(tags=["extra"])


# ================================================================ Birgalikda to'laymiz / Orzu
class SplitIn(BaseModel):
    mode: str = Field(pattern="^(split|wish)$")
    package_id: int
    player_id: str = Field("", max_length=64)
    zone_id: str = Field("", max_length=64)
    message: str = Field("", max_length=200)


@router.post("/split")
async def split_create(body: SplitIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"split:{user.id}", limit=20, window=3600)
    async with session.begin():
        s = await split.create(session, user.id, body.mode, body.package_id, body.player_id, body.zone_id, body.message)
        code = s.code
    return await split.view(session, code, user.id, settings.bot_username)


@router.get("/split/my")
async def split_my(user: CurrentUser, session: SessionDep):
    return await split.my(session, user.id)


@router.get("/split/{code}")
async def split_get(code: str, user: CurrentUser, session: SessionDep):
    return await split.view(session, code, user.id, settings.bot_username)


class PayIn(BaseModel):
    amount: int = Field(gt=0, le=100_000_000)


@router.post("/split/{code}/pay")
async def split_pay(code: str, body: PayIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"splitpay:{user.id}", limit=30, window=600)
    out = Outbox()
    async with session.begin():
        _, order_id = await split.contribute(session, user.id, code, body.amount, out)
    await out.flush()
    if order_id:
        await enqueue("fulfil_donate", order_id, "create")
    return await split.view(session, code, user.id, settings.bot_username)


@router.post("/split/{code}/cancel")
async def split_cancel(code: str, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await split.cancel(session, user.id, code, out)
    await out.flush()
    return await split.view(session, code, user.id, settings.bot_username)


# ================================================================ Draft Jang
@router.post("/duel")
async def duel_create(user: CurrentUser, session: SessionDep):
    await rate_limit(f"duel:{user.id}", limit=20, window=3600)
    async with session.begin():
        d = await duel.create(session, user.id)
        code = d.code
    return await duel.view(session, code, user.id, settings.bot_username)


@router.get("/duel/top")
async def duel_top(user: CurrentUser, session: SessionDep):
    return {"items": await duel.top(session), "me": {"elo": user.draft_elo}}


@router.get("/duel/{code}")
async def duel_get(code: str, user: CurrentUser, session: SessionDep):
    return await duel.view(session, code, user.id, settings.bot_username)


@router.post("/duel/{code}/join")
async def duel_join(code: str, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await duel.join(session, user.id, code, out)
    await out.flush()
    return await duel.view(session, code, user.id, settings.bot_username)


class PicksIn(BaseModel):
    picks: dict[str, int]


@router.post("/duel/{code}/picks")
async def duel_picks(code: str, body: PicksIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        _, ready = await duel.submit(session, user.id, code, body.picks, out)
    if ready:
        async with session.begin():
            await duel.resolve(session, code, out)
    await out.flush()
    return await duel.view(session, code, user.id, settings.bot_username)


# ================================================================ Kunlik seriya, Meta bashorat
@router.get("/habit")
async def habit_get(user: CurrentUser, session: SessionDep):
    return await habit.status(session, user)


@router.post("/habit/checkin")
async def habit_checkin(user: CurrentUser, session: SessionDep):
    async with session.begin():
        return await habit.checkin(session, user.id)


@router.get("/meta")
async def meta_get(user: CurrentUser, session: SessionDep):
    async with session.begin():
        return await habit.meta_state(session, user.id)


class MetaIn(BaseModel):
    hero_id: int


@router.post("/meta/pick")
async def meta_pick(body: MetaIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        return await habit.meta_pick(session, user.id, body.hero_id)


# ================================================================ O'yinchi kartasi
@router.post("/arena/card")
async def player_card(user: CurrentUser, session: SessionDep):
    """Karta rasmini botdan o'ziga yuboradi (ulashish uchun). QR — foydalanuvchining taklif havolasi."""
    from aiogram.types import BufferedInputFile

    from app.bot.instance import get_bot

    await rate_limit(f"pcard:{user.id}", limit=5, window=600)
    if not settings.bot_username:
        raise BadState("Bot manzili sozlanmagan")
    ref = f"https://t.me/{settings.bot_username}?startapp=ref_{user.id}"
    from app.services import vay

    v = await vay.overview(session, user)
    place = ((await arena.leaderboard(session, user.id)).get("me") or {}).get("place")
    png = card.player_card_png(user.ml_nick or user.first_name or "Player", user.ml_rank or "", user.ml_lane or "", list(user.ml_heroes or []),
                               v["name"], v["xp"], user.draft_elo, user.streak_days or 0, place, ref)
    await get_bot().send_photo(user.id, BufferedInputFile(png, "karta.png"),
                               caption=f"🪪 Mening MLBB kartam\n\nDo'stlaringizga yuboring: havola orqali kirganlar sizning taklifingiz bo'ladi.\n{ref}")
    return {"ok": True}
