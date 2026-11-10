"""Akkaunt savdo: e'lon -> chat -> garantli bitim -> tasdiq/nizo -> baho.

Bitim holatlari:
  paid       — xaridor to'ladi, pul platformada; sotuvchi ma'lumotlarni yuborishi kerak
  delivered  — sotuvchi login/parolni yubordi; xaridor tekshiradi (yoki N soatdan so'ng avto-tasdiq)
  completed  — pul sotuvchiga o'tdi (komissiyasiz)
  disputed   — nizo: admin hal qiladi
  refunded   — pul xaridorga qaytdi
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError, BadState, Forbidden, NotFound
from app.models import Chat, Deal, Listing, Message, Review
from app.security import decrypt, encrypt
from app.services import wallet
from app.services.notify import Outbox, fmt, webapp_button

SELLER_DELIVER_HOURS = 12
VERIFIED_SALES = 5  # shuncha muvaffaqiyatli savdodan keyin "Tasdiqlangan sotuvchi"  # sotuvchi shu vaqtda ma'lumot bermasa, xaridor bitimni bekor qila oladi
MAX_MEDIA = 6
GAMES = ("ML", "MC")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ e'lonlar
def validate_listing_data(data: dict) -> dict:
    if data.get("game") not in GAMES:
        raise AppError("bad_game", "O'yinni tanlang")
    title = (data.get("title") or "").strip()
    if not 3 <= len(title) <= 120:
        raise AppError("bad_title", "Sarlavha 3–120 belgi bo'lishi kerak")
    price = int(data.get("price") or 0)
    if not 1_000 <= price <= 500_000_000:
        raise AppError("bad_price", "Narx 1 000 so'mdan kam bo'lmasin")
    media = data.get("media") or []
    if len(media) > MAX_MEDIA:
        raise AppError("too_many_media", f"Ko'pi bilan {MAX_MEDIA} ta rasm/video")
    clean_media = []
    for m in media:
        url = str(m.get("url", ""))
        if not url.startswith(settings.media_url + "/"):
            raise AppError("bad_media", "Media faqat ilova orqali yuklanadi")
        clean_media.append({"type": "video" if m.get("type") == "video" else "image", "url": url})
    return {
        "game": data["game"],
        "title": title,
        "rank": (data.get("rank") or "").strip()[:32],
        "server": (data.get("server") or "").strip()[:32],
        "collection_level": (data.get("collection_level") or "").strip()[:32],
        "skins": max(0, min(int(data.get("skins") or 0), 5000)),
        "heroes": max(0, min(int(data.get("heroes") or 0), 500)),
        "price": price,
        "description": (data.get("description") or "").strip()[:3000],
        "media": clean_media,
    }


async def create_listing(session: AsyncSession, seller_id: int, data: dict, out: Outbox) -> Listing:
    listing = Listing(seller_id=seller_id, status="moderation", **validate_listing_data(data))
    session.add(listing)
    await session.flush()
    out.admins(f"🆕 Yangi e'lon moderatsiyada: #{listing.id} · {listing.title} · {fmt(listing.price)}", webapp_button("Ko'rib chiqish", "/admin"))
    return listing


async def update_listing(session: AsyncSession, seller_id: int, listing_id: int, data: dict) -> Listing:
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id).with_for_update().execution_options(populate_existing=True))
    if listing is None or listing.seller_id != seller_id:
        raise NotFound("E'lon")
    if listing.status not in ("active", "moderation", "rejected", "closed"):
        raise BadState("Bitim jarayonidagi e'lonni tahrirlab bo'lmaydi")
    for k, v in validate_listing_data(data).items():
        setattr(listing, k, v)
    listing.status = "moderation"  # tahrirdan keyin qayta tekshiriladi
    listing.reject_reason = None
    return listing


async def close_listing(session: AsyncSession, seller_id: int, listing_id: int) -> Listing:
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id).with_for_update().execution_options(populate_existing=True))
    if listing is None or listing.seller_id != seller_id:
        raise NotFound("E'lon")
    if listing.status in ("reserved", "sold"):
        raise BadState("Bitim jarayonidagi e'lonni yopib bo'lmaydi")
    listing.status = "closed"
    return listing


async def moderate_listing(session: AsyncSession, listing_id: int, approve: bool, reason: str | None, out: Outbox) -> Listing:
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id).with_for_update().execution_options(populate_existing=True))
    if listing is None:
        raise NotFound("E'lon")
    if listing.status != "moderation":
        raise BadState("E'lon moderatsiyada emas")
    if approve:
        listing.status = "active"
        out.user(listing.seller_id, f"✅ E'loningiz tasdiqlandi: {listing.title}", webapp_button("Ko'rish", f"/listing/{listing.id}"))
    else:
        listing.status = "rejected"
        listing.reject_reason = (reason or "Qoidalarga mos emas")[:300]
        out.user(listing.seller_id, f"❌ E'lon rad etildi: {listing.title}\nSabab: {listing.reject_reason}", webapp_button("Mening e'lonlarim", "/my-listings"))
    return listing


# ------------------------------------------------------------------ chat
async def open_chat(session: AsyncSession, listing_id: int, buyer_id: int) -> Chat:
    listing = await session.get(Listing, listing_id)
    if listing is None or listing.status not in ("active", "reserved", "sold"):
        raise NotFound("E'lon")
    if listing.seller_id == buyer_id:
        raise AppError("own_listing", "O'z e'loningizga yozib bo'lmaydi")
    chat = await session.scalar(select(Chat).where(Chat.listing_id == listing_id, Chat.buyer_id == buyer_id))
    if chat is None:
        chat = Chat(listing_id=listing_id, buyer_id=buyer_id, seller_id=listing.seller_id, listing=listing)
        session.add(chat)
        await session.flush()
    return chat


async def get_chat_for(session: AsyncSession, chat_id: int, user_id: int, is_admin: bool = False) -> Chat:
    chat = await session.get(Chat, chat_id)
    if chat is None or (user_id not in (chat.buyer_id, chat.seller_id) and not is_admin):
        raise NotFound("Chat")
    return chat


async def send_message(session: AsyncSession, chat: Chat, sender_id: int | None, text: str, out: Outbox) -> Message:
    text = (text or "").strip()
    if not text or len(text) > 2000:
        raise AppError("bad_message", "Xabar 1–2000 belgi bo'lishi kerak")
    msg = Message(chat_id=chat.id, sender_id=sender_id, text=text)
    session.add(msg)
    chat.last_message_at = _now()
    await session.flush()
    if sender_id is not None:
        to = chat.seller_id if sender_id == chat.buyer_id else chat.buyer_id
        out.user(to, f"💬 Yangi xabar ({chat.listing.title}):\n{text[:200]}", webapp_button("Javob berish", f"/chat/{chat.id}"), kind="chat")
    return msg


async def _system(session: AsyncSession, chat_id: int, text: str) -> None:
    session.add(Message(chat_id=chat_id, sender_id=None, text=text))


# ------------------------------------------------------------------ bitim
async def lock_deal(session: AsyncSession, deal_id: int) -> Deal:
    deal = await session.scalar(select(Deal).where(Deal.id == deal_id).with_for_update().execution_options(populate_existing=True))
    if deal is None:
        raise NotFound("Bitim")
    return deal


async def buy(session: AsyncSession, listing_id: int, buyer_id: int, out: Outbox) -> Deal:
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id).with_for_update().execution_options(populate_existing=True))
    if listing is None:
        raise NotFound("E'lon")
    if listing.status != "active":
        raise BadState("Bu akkaunt allaqachon sotilgan yoki band")
    if listing.seller_id == buyer_id:
        raise AppError("own_listing", "O'z akkauntingizni sotib ololmaysiz")
    chat = await open_chat(session, listing_id, buyer_id)
    commission = listing.price * settings.commission_percent // 100
    deal = Deal(
        listing_id=listing.id,
        buyer_id=buyer_id,
        seller_id=listing.seller_id,
        chat_id=chat.id,
        price=listing.price,
        commission=commission,
        status="paid",
        listing=listing,
    )
    session.add(deal)
    await session.flush()
    await wallet.debit(session, buyer_id, listing.price, "deal_pay", f"deal:{deal.id}:pay", ref_type="deal", ref_id=deal.id)
    listing.status = "reserved"
    await _system(session, chat.id, f"🔒 Xaridor {fmt(deal.price)} to'ladi. Pul VAYNEXO garantida. Sotuvchi akkaunt ma'lumotlarini yuborsin.")
    out.user(
        listing.seller_id,
        f"💰 Akkauntingiz sotib olindi: {listing.title}\nPul garantda: {fmt(deal.price)}.\n"
        f"{SELLER_DELIVER_HOURS} soat ichida akkaunt ma'lumotlarini yuboring.",
        webapp_button("Bitimni ochish", f"/deal/{deal.id}"),
    )
    return deal


async def deliver(session: AsyncSession, deal_id: int, seller_id: int, credentials: str, out: Outbox) -> Deal:
    deal = await lock_deal(session, deal_id)
    if deal.seller_id != seller_id:
        raise Forbidden()
    if deal.status != "paid":
        raise BadState()
    credentials = (credentials or "").strip()
    if not 3 <= len(credentials) <= 2000:
        raise AppError("bad_credentials", "Akkaunt ma'lumotlarini kiriting")
    deal.credentials_enc = encrypt(credentials)
    deal.status = "delivered"
    deal.delivered_at = _now()
    deal.auto_release_at = _now() + timedelta(hours=settings.escrow_auto_release_hours)
    await _system(
        session, deal.chat_id,
        f"📦 Sotuvchi akkaunt ma'lumotlarini yubordi. Tekshirib, tasdiqlang. "
        f"{settings.escrow_auto_release_hours} soat ichida nizo ochilmasa, bitim avtomatik yakunlanadi.",
    )
    out.user(
        deal.buyer_id,
        f"📦 Akkaunt ma'lumotlari tayyor: {deal.listing.title}\nTekshirib, «Tasdiqlash» ni bosing. Muammo bo'lsa — «Nizo ochish».",
        webapp_button("Bitimni ochish", f"/deal/{deal.id}"),
    )
    return deal


async def _complete(session: AsyncSession, deal: Deal, out: Outbox, note: str) -> None:
    deal.status = "completed"
    deal.finished_at = _now()
    deal.auto_release_at = None
    payout = deal.price - deal.commission
    await wallet.credit(session, deal.seller_id, payout, "deal_payout", f"deal:{deal.id}:payout", ref_type="deal", ref_id=deal.id)
    listing = await session.scalar(select(Listing).where(Listing.id == deal.listing_id).with_for_update().execution_options(populate_existing=True))
    listing.status = "sold"
    await wallet.add_ticket(session, deal.buyer_id)
    await _system(session, deal.chat_id, f"✅ Bitim yakunlandi ({note}).")
    out.user(deal.seller_id, f"✅ Bitim yakunlandi: {listing.title}\nHamyoningizga: +{fmt(payout)} (komissiya {fmt(deal.commission)})")
    out.user(deal.buyer_id, f"✅ Bitim yakunlandi: {listing.title}. Sotuvchini baholashni unutmang!", webapp_button("Baholash", f"/deal/{deal.id}"))


async def _refund(session: AsyncSession, deal: Deal, out: Outbox, note: str, relist: bool) -> None:
    deal.status = "refunded"
    deal.finished_at = _now()
    deal.auto_release_at = None
    await wallet.credit(session, deal.buyer_id, deal.price, "deal_refund", f"deal:{deal.id}:refund", ref_type="deal", ref_id=deal.id)
    listing = await session.scalar(select(Listing).where(Listing.id == deal.listing_id).with_for_update().execution_options(populate_existing=True))
    listing.status = "active" if relist else "closed"
    await _system(session, deal.chat_id, f"↩️ Pul xaridorga qaytarildi ({note}).")
    out.user(deal.buyer_id, f"↩️ {fmt(deal.price)} hamyoningizga qaytarildi: {listing.title}")
    out.user(deal.seller_id, f"↩️ Bitim bekor qilindi: {listing.title} ({note})")


async def confirm(session: AsyncSession, deal_id: int, buyer_id: int, out: Outbox) -> Deal:
    deal = await lock_deal(session, deal_id)
    if deal.buyer_id != buyer_id:
        raise Forbidden()
    if deal.status != "delivered":
        raise BadState()
    await _complete(session, deal, out, "xaridor tasdiqladi")
    return deal


async def cancel(session: AsyncSession, deal_id: int, user_id: int, out: Outbox) -> Deal:
    """Sotuvchi istalgan vaqtda (ma'lumot berguncha) yoki xaridor muddat o'tgach bekor qila oladi."""
    deal = await lock_deal(session, deal_id)
    if user_id not in (deal.buyer_id, deal.seller_id):
        raise Forbidden()
    if deal.status != "paid":
        raise BadState("Ma'lumot yuborilgandan keyin bekor qilib bo'lmaydi — nizo oching")
    if user_id == deal.buyer_id and _now() < deal.created_at + timedelta(hours=SELLER_DELIVER_HOURS):
        raise BadState(f"Sotuvchiga {SELLER_DELIVER_HOURS} soat beriladi. Undan keyin bekor qilishingiz mumkin")
    who = "sotuvchi bekor qildi" if user_id == deal.seller_id else "sotuvchi javob bermadi"
    await _refund(session, deal, out, who, relist=user_id == deal.buyer_id)
    return deal


async def open_dispute(session: AsyncSession, deal_id: int, user_id: int, reason: str, out: Outbox) -> Deal:
    deal = await lock_deal(session, deal_id)
    if user_id not in (deal.buyer_id, deal.seller_id):
        raise Forbidden()
    if deal.status not in ("paid", "delivered"):
        raise BadState()
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise AppError("bad_reason", "Muammoni batafsil yozing")
    deal.status = "disputed"
    deal.dispute_reason = reason[:2000]
    deal.auto_release_at = None
    await _system(session, deal.chat_id, "⚖️ Nizo ochildi. Pul muzlatildi, admin ikkala tomonni ko'rib chiqadi.")
    other = deal.seller_id if user_id == deal.buyer_id else deal.buyer_id
    out.user(other, f"⚖️ Bitim #{deal.id} bo'yicha nizo ochildi. Admin bog'lanadi.", webapp_button("Bitimni ochish", f"/deal/{deal.id}"))
    out.admins(f"⚖️ Nizo: bitim #{deal.id} · {fmt(deal.price)}\nSabab: {reason[:500]}", webapp_button("Admin panel", "/admin"))
    return deal


async def resolve_dispute(session: AsyncSession, deal_id: int, winner: str, note: str, out: Outbox) -> Deal:
    deal = await lock_deal(session, deal_id)
    if deal.status != "disputed":
        raise BadState("Bitimda nizo yo'q")
    deal.resolution = (note or "")[:300]
    if winner == "seller":
        await _complete(session, deal, out, "admin qarori")
    elif winner == "buyer":
        await _refund(session, deal, out, "admin qarori", relist=False)
    else:
        raise AppError("bad_action", "winner: seller | buyer")
    return deal


async def auto_release(session: AsyncSession, out: Outbox, limit: int = 100) -> int:
    ids = list(
        await session.scalars(
            select(Deal.id).where(Deal.status == "delivered", Deal.auto_release_at <= _now()).limit(limit)
        )
    )
    done = 0
    for deal_id in ids:
        deal = await lock_deal(session, deal_id)
        if deal.status == "delivered" and deal.auto_release_at and deal.auto_release_at <= _now():
            await _complete(session, deal, out, "avtomatik tasdiq")
            done += 1
    return done


def credentials_for(deal: Deal, user_id: int, is_admin: bool = False) -> str | None:
    """Login/parolni faqat xaridor (va admin) ko'radi."""
    if deal.status not in ("delivered", "completed", "disputed"):
        return None
    if user_id == deal.buyer_id or is_admin:
        return decrypt(deal.credentials_enc)
    return None


# ------------------------------------------------------------------ baho
async def review(session: AsyncSession, deal_id: int, buyer_id: int, score: int, tags: list[str], text: str) -> Review:
    deal = await session.get(Deal, deal_id)
    if deal is None or deal.buyer_id != buyer_id:
        raise NotFound("Bitim")
    if deal.status != "completed":
        raise BadState("Faqat yakunlangan bitimni baholash mumkin")
    if not 1 <= score <= 5:
        raise AppError("bad_score", "Baho 1 dan 5 gacha")
    if await session.scalar(select(Review.id).where(Review.deal_id == deal_id)):
        raise BadState("Siz allaqachon baho bergansiz")
    r = Review(deal_id=deal_id, from_id=buyer_id, to_id=deal.seller_id, score=score,
               tags=[str(t)[:32] for t in tags[:6]], text=(text or "").strip()[:500])
    session.add(r)
    seller = await wallet.lock_user(session, deal.seller_id)
    seller.rating_sum += score
    seller.rating_count += 1
    return r


async def seller_stats(session: AsyncSession, user_id: int) -> dict:
    sales = await session.scalar(
        select(func.count()).select_from(Deal).where(Deal.seller_id == user_id, Deal.status == "completed")
    ) or 0
    positive = await session.scalar(
        select(func.count()).select_from(Review).where(Review.to_id == user_id, Review.score >= 4)
    ) or 0
    total = await session.scalar(select(func.count()).select_from(Review).where(Review.to_id == user_id)) or 0
    return {"sales": sales, "positive_percent": round(positive * 100 / total) if total else None}


# ------------------------------------------------------------------ VIP e'lon
async def buy_vip(session: AsyncSession, seller_id: int, listing_id: int, days: int) -> Listing:
    from app.services import app_settings

    listing = await session.scalar(select(Listing).where(Listing.id == listing_id).with_for_update().execution_options(populate_existing=True))
    if listing is None or listing.seller_id != seller_id:
        raise NotFound("E'lon")
    if listing.status != "active":
        raise BadState("VIP faqat faol (tasdiqlangan) e'longa qo'yiladi")
    if not 1 <= days <= 30:
        raise AppError("bad_days", "1 dan 30 kungacha")
    price = await app_settings.get_value(session, "vip_price_per_day") * days
    if price > 0:
        await wallet.debit(session, seller_id, price, "vip", f"vip:{listing_id}:{_now().timestamp()}", ref_type="listing", ref_id=listing_id,
                           note=f"VIP {days} kun")
    start = listing.vip_until if listing.vip_until and listing.vip_until > _now() else _now()
    listing.vip_until = start + timedelta(days=days)
    return listing
