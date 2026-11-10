"""Sozlamalar: identifikatsiya, PIN-kod, biometriya, bildirishnomalar, saqlangan kartalar."""

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AdminUser, CurrentUser, SessionDep, rate_limit
from app.api.media import IMAGE_MAX, _read_limited
from app.errors import AppError
from app.models import User
from app.security import check_secret, make_pin_token
from app.services import account as acc
from app.services.notify import Outbox

router = APIRouter(tags=["account"])


# ---------------------------------------------------------------- Identifikatsiya
@router.post("/me/kyc")
async def kyc_submit(selfie: UploadFile, front: UploadFile, back: UploadFile, user: CurrentUser, session: SessionDep):
    await rate_limit(f"kyc:{user.id}", limit=3, window=3600)
    images = []
    for f in (selfie, front, back):
        if not (f.content_type or "").startswith("image/"):
            raise AppError("bad_image", "Faqat rasm yuklang")
        images.append(await _read_limited(f, IMAGE_MAX))
    u = await acc.kyc_submit(session, user.id, images)
    return {"kyc_status": u.kyc_status}


@router.get("/admin/kyc")
async def kyc_pending(admin: AdminUser, session: SessionDep):
    rows = await session.scalars(select(User).where(User.kyc_status == "pending").order_by(User.kyc_at).limit(100))
    return [{"id": u.id, "name": u.first_name, "username": u.username, "at": u.kyc_at.isoformat() if u.kyc_at else None} for u in rows]


class KycResolveIn(BaseModel):
    approve: bool
    note: str | None = Field(None, max_length=300)


@router.post("/admin/kyc/{user_id}")
async def kyc_resolve(user_id: int, body: KycResolveIn, admin: AdminUser, session: SessionDep):
    out = Outbox()
    u = await acc.kyc_resolve(session, user_id, body.approve, body.note, out)
    await out.flush()
    return {"id": u.id, "kyc_status": u.kyc_status}


# ---------------------------------------------------------------- PIN-kod
class PinIn(BaseModel):
    pin: str = Field(max_length=8)
    old_pin: str | None = Field(None, max_length=8)


@router.post("/me/pin")
async def pin_set(body: PinIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"pin:{user.id}", limit=10, window=900)
    u = await acc.set_pin(session, user.id, body.pin, body.old_pin)
    return {"pin_set": True, "bio_set": False, "token": make_pin_token(u.id, u.pin_ver)}


class PinOnly(BaseModel):
    pin: str = Field(max_length=8)


@router.post("/me/pin/remove")
async def pin_remove(body: PinOnly, user: CurrentUser, session: SessionDep):
    await rate_limit(f"pin:{user.id}", limit=10, window=900)
    await acc.remove_pin(session, user.id, body.pin)
    return {"pin_set": False, "bio_set": False}


@router.post("/me/pin/verify")
async def pin_verify(body: PinOnly, user: CurrentUser):
    await rate_limit(f"pinv:{user.id}", limit=10, window=900)
    if not user.pin_hash:
        return {"token": None}
    if not check_secret(body.pin, user.pin_hash):
        raise AppError("wrong_pin", "PIN noto'g'ri", 403)
    return {"token": make_pin_token(user.id, user.pin_ver)}


class BioIn(BaseModel):
    key: str = Field(max_length=100)


@router.post("/me/pin/bio")
async def bio_enable(body: PinOnly, user: CurrentUser, session: SessionDep):
    """Biometriyani yoqish PIN bilan tasdiqlanadi; qaytgan kalit qurilmaning biometrik xotirasida saqlanadi."""
    await rate_limit(f"pin:{user.id}", limit=10, window=900)
    if not check_secret(body.pin, user.pin_hash):
        raise AppError("wrong_pin", "PIN noto'g'ri", 403)
    return {"key": await acc.enable_bio(session, user.id)}


@router.post("/me/pin/bio/off")
async def bio_disable(user: CurrentUser, session: SessionDep):
    await acc.disable_bio(session, user.id)
    return {"bio_set": False}


@router.post("/me/pin/bio/verify")
async def bio_verify(body: BioIn, user: CurrentUser):
    await rate_limit(f"pinv:{user.id}", limit=10, window=900)
    if not user.pin_hash or not check_secret(body.key, user.bio_hash):
        raise AppError("wrong_bio", "Biometrik kalit eskirgan. PIN bilan kiring", 403)
    return {"token": make_pin_token(user.id, user.pin_ver)}


# ---------------------------------------------------------------- Kartalar
@router.get("/me/cards")
async def cards(user: CurrentUser, session: SessionDep):
    return [acc.card_dict(c) for c in await acc.list_cards(session, user.id)]


class CardIn(BaseModel):
    number: str = Field(max_length=32)
    holder: str = Field("", max_length=64)
    expiry: str = Field("", max_length=5)


@router.post("/me/cards")
async def card_add(body: CardIn, user: CurrentUser, session: SessionDep):
    c = await acc.add_card(session, user.id, body.number, body.holder, body.expiry)
    return acc.card_dict(c)


@router.post("/me/cards/{card_id}/default")
async def card_default(card_id: int, user: CurrentUser, session: SessionDep):
    await acc.set_default_card(session, user.id, card_id)
    return {"ok": True}


@router.delete("/me/cards/{card_id}")
async def card_delete(card_id: int, user: CurrentUser, session: SessionDep):
    await acc.delete_card(session, user.id, card_id)
    return {"ok": True}


# ---------------------------------------------------------------- Yordam
class SupportIn(BaseModel):
    text: str = Field(min_length=5, max_length=1500)


@router.post("/support")
async def support(body: SupportIn, user: CurrentUser):
    """Foydalanuvchi muammosi adminlarga botda yuboriladi."""
    await rate_limit(f"support:{user.id}", limit=3, window=600)
    who = f"@{user.username}" if user.username else user.first_name
    out = Outbox()
    out.admins(f"🆘 Yordam so'rovi\n{who} · ID {user.id}\n\n{body.text.strip()}")
    await out.flush()
    return {"ok": True}
