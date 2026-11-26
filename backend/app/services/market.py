"""Akkaunt savdo: e'lon -> chat -> garantli bitim -> tasdiq/nizo -> baho.

Bitim holatlari:
  paid       — xaridor to'ladi, pul platformada; sotuvchi ma'lumotlarni yuborishi kerak
  delivered  — sotuvchi login/parolni yubordi; xaridor tekshiradi (yoki N kundan so'ng avto-tasdiq)
  holding    — xaridor tasdiqladi, lekin pul yana bir necha kun platformada ushlanadi: sotuvchi akkauntni
               qaytarib olmaganiga ishonch hosil qilish uchun. Shu paytda ham nizo ochish mumkin
  completed  — pul sotuvchiga o'tdi
  disputed   — nizo: admin hal qiladi
  refunded   — pul xaridorga qaytdi
"""

import hashlib
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError, BadState, Forbidden, NotFound
from app.models import Chat, Deal, Listing, Message, Review, User
from app.security import decrypt, encrypt
from app.services import wallet
from app.services.notify import Outbox, fmt, webapp_button

SELLER_DELIVER_HOURS = 12  # standart; haqiqiy qiymat — «deliver_hours» sozlamasi
WARN_BEFORE = timedelta(hours=3)
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


def account_fields(data: dict, required: bool) -> tuple[str, str] | None:
    """Akkaunt ID (User ID + Zone ID) -> (xesh, shifrlangan). Xesh bir akkaunt ikki marta sotilmasligi uchun."""
    gid, zid = str(data.get("game_id") or "").strip(), str(data.get("zone_id") or "").strip()
    if not gid and not zid and not required:
        return None
    if not re.fullmatch(r"\d{5,20}", gid) or not re.fullmatch(r"\d{1,10}", zid):
        raise AppError("bad_account_id", "Akkauntning MLBB User ID va Zone ID sini to'g'ri kiriting (e'londa ko'rsatilmaydi)")
    raw = f"{data.get('game')}:{gid}:{zid}"
    return hashlib.sha256(raw.encode()).hexdigest(), encrypt(raw)


async def _check_listing(session: AsyncSession, seller_id: int, clean: dict, acc: tuple[str, str] | None, listing_id: int | None) -> None:
    from app.services import app_settings

    need = int(await app_settings.get_value(session, "market_min_photos"))
    photos = sum(1 for m in clean["media"] if m["type"] == "image")
    if photos < need:
        raise AppError("few_photos", f"Kamida {need} ta rasm yuklang: profil (ID bilan), rank va skinlar/kolleksiya")
    if acc:
        q = select(Listing.id).where(Listing.account_key == acc[0], Listing.status.in_(("moderation", "active", "reserved")))
        if listing_id:
            q = q.where(Listing.id != listing_id)
        if await session.scalar(q.limit(1)):
            raise AppError("dup_account", "Bu akkaunt allaqachon sotuvga qo'yilgan", 409)


async def create_listing(session: AsyncSession, seller_id: int, data: dict, out: Outbox) -> Listing:
    from app.services import app_settings
    from app.services.account import require_kyc

    await require_kyc(session, seller_id, "marketplace")
    seller = await session.get(User, seller_id)
    if seller.seller_strikes >= int(await app_settings.get_value(session, "strikes_block")):
        raise AppError("seller_blocked", "Bitimlarda muddatni qayta-qayta buzganingiz uchun e'lon qo'sha olmaysiz. Support'ga yozing", 403)
    clean = validate_listing_data(data)
    acc = account_fields(data, required=await app_settings.get_value(session, "market_account_id") == "on")
    await _check_listing(session, seller_id, clean, acc, None)
    listing = Listing(seller_id=seller_id, status="moderation", account_key=acc[0] if acc else None, account_enc=acc[1] if acc else None, **clean)
    session.add(listing)
    await session.flush()
    out.admins(f"🆕 Yangi e'lon moderatsiyada: #{listing.id} · {listing.title} · {fmt(listing.price)}", webapp_button("Ko'rib chiqish", "/admin"), topic="elon")
    return listing


async def update_listing(session: AsyncSession, seller_id: int, listing_id: int, data: dict) -> Listing:
    listing = await session.scalar(select(Listing).where(Listing.id == listing_id).with_for_update().execution_options(populate_existing=True))
    if listing is None or listing.seller_id != seller_id:
        raise NotFound("E'lon")
    if listing.status not in ("active", "moderation", "rejected", "closed"):
        raise BadState("Bitim jarayonidagi e'lonni tahrirlab bo'lmaydi")
    clean = validate_listing_data(data)
    acc = account_fields(data, required=False)
    await _check_listing(session, seller_id, clean, acc, listing.id)
    for k, v in clean.items():
        setattr(listing, k, v)
    if acc:
        listing.account_key, listing.account_enc = acc
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


_CONTACT_RES = (
    re.compile(r"(https?://|www\.|t\.me/|\b[a-z0-9-]+\.(com|uz|ru|me|org|net|io)\b)", re.I),
    re.compile(r"(?:\+?\d[\s\-().]?){9,}"),
    re.compile(r"@[a-z0-9_]{4,}", re.I),
    re.compile(r"\b(whats\s?app|watsap|vatsap|instagram|insta|lichka|lichkaga|karta\s*raqam|payme|uzcard|humo)\b", re.I),
)


def has_contact(text: str) -> bool:
    """Telefon, havola, @nik, karta — garantdan tashqarida savdo qilishga urinish."""
    return any(r.search(text) for r in _CONTACT_RES)


async def send_message(session: AsyncSession, chat: Chat, sender_id: int | None, text: str, out: Outbox) -> Message:
    text = (text or "").strip()
    if not text or len(text) > 2000:
        raise AppError("bad_message", "Xabar 1–2000 belgi bo'lishi kerak")
    if sender_id is not None:
        from app.services import app_settings

        if await app_settings.get_value(session, "chat_block_contacts") == "on" and has_contact(text):
            raise AppError("contact_blocked", "Telefon, havola, @nik va karta raqamini yozib bo'lmaydi. Garantdan tashqarida savdo qilsangiz, "
                                              "pulingiz himoyasiz qoladi — bitimni faqat VAYNEXO orqali qiling.")
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
    from app.services import app_settings
    from app.services.account import require_kyc

    await require_kyc(session, buyer_id, "marketplace")
    chat = await open_chat(session, listing_id, buyer_id)
    commission = listing.price * int(await app_settings.get_value(session, "garant_fee_percent")) // 100
    hours = int(await app_settings.get_value(session, "deliver_hours"))
    deal = Deal(
        listing_id=listing.id,
        buyer_id=buyer_id,
        seller_id=listing.seller_id,
        chat_id=chat.id,
        price=listing.price,
        commission=commission,
        status="paid",
        listing=listing,
        deliver_by=_now() + timedelta(hours=hours),
    )
    session.add(deal)
    await session.flush()
    await wallet.debit(session, buyer_id, listing.price, "deal_pay", f"deal:{deal.id}:pay", ref_type="deal", ref_id=deal.id)
    listing.status = "reserved"
    await _system(session, chat.id, f"🔒 Xaridor {fmt(deal.price)} to'ladi. Pul VAYNEXO garantida. Sotuvchi {hours} soat ichida akkaunt ma'lumotlarini yuborishi kerak.")
    out.user(
        listing.seller_id,
        f"💰 Akkauntingiz sotib olindi: {listing.title}\nPul garantda: {fmt(deal.price)}.\n"
        f"{hours} soat ichida akkaunt ma'lumotlarini yuboring, aks holda bitim bekor bo'lib, pul xaridorga qaytadi va hisobingizga ogohlantirish yoziladi.",
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
    from app.services import app_settings

    days = int(await app_settings.get_value(session, "escrow_release_days"))
    deal.auto_release_at = _now() + timedelta(days=days)
    await _system(
        session, deal.chat_id,
        f"📦 Sotuvchi akkaunt ma'lumotlarini yubordi. Tekshirib, tasdiqlang. "
        f"{days} kun ichida nizo ochilmasa, bitim avtomatik yakunlanadi.",
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


async def _seller_hold_days(session: AsyncSession, seller_id: int) -> int:
    from app.services import app_settings

    stats = await seller_stats(session, seller_id)
    seller = await session.get(User, seller_id)
    trusted = stats["sales"] >= VERIFIED_SALES and (seller.seller_strikes or 0) == 0
    return int(await app_settings.get_value(session, "hold_days_verified" if trusted else "hold_days_new"))


async def _confirm_or_hold(session: AsyncSession, deal: Deal, out: Outbox, note: str) -> None:
    """Xaridor tasdiqladi (yoki muddat o'tdi): pul darhol emas, himoya muddatidan keyin sotuvchiga o'tadi."""
    days = await _seller_hold_days(session, deal.seller_id)
    if days <= 0:
        await _complete(session, deal, out, note)
        return
    deal.status = "holding"
    deal.confirmed_at = _now()
    deal.hold_until = _now() + timedelta(days=days)
    deal.auto_release_at = None
    title = deal.listing.title
    await _system(session, deal.chat_id, f"🛡 Akkaunt qabul qilindi ({note}). Pul {days} kun himoya muddatida: sotuvchi akkauntni qaytarib olmaganiga "
                                         "ishonch hosil qilingach o'tadi. Shu muddatda muammo bo'lsa — «Nizo ochish».")
    out.user(deal.seller_id, f"🛡 «{title}» qabul qilindi. {fmt(deal.price - deal.commission)} {days} kundan keyin hamyoningizga tushadi.")
    out.user(deal.buyer_id, f"🛡 Akkaunt qabul qilindi: {title}. Birinchi navbatda login, parol va emailni o'zgartiring va eski bog'lanishlarni uzing. "
                            f"{days} kun ichida akkaunt qaytarib olinsa — «Nizo ochish» ni bosing.", webapp_button("Bitimni ochish", f"/deal/{deal.id}"))


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
    await _confirm_or_hold(session, deal, out, "xaridor tasdiqladi")
    return deal


async def cancel(session: AsyncSession, deal_id: int, user_id: int, out: Outbox) -> Deal:
    """Sotuvchi istalgan vaqtda (ma'lumot berguncha) yoki xaridor muddat o'tgach bekor qila oladi."""
    deal = await lock_deal(session, deal_id)
    if user_id not in (deal.buyer_id, deal.seller_id):
        raise Forbidden()
    if deal.status != "paid":
        raise BadState("Ma'lumot yuborilgandan keyin bekor qilib bo'lmaydi — nizo oching")
    deadline = deal.deliver_by or deal.created_at + timedelta(hours=SELLER_DELIVER_HOURS)
    if user_id == deal.buyer_id and _now() < deadline:
        raise BadState("Sotuvchiga ma'lumot berish uchun muddat beriladi. Muddat tugagach pul avtomatik qaytadi")
    who = "sotuvchi bekor qildi" if user_id == deal.seller_id else "sotuvchi javob bermadi"
    await _refund(session, deal, out, who, relist=user_id == deal.buyer_id)
    return deal


async def open_dispute(session: AsyncSession, deal_id: int, user_id: int, reason: str, out: Outbox) -> Deal:
    deal = await lock_deal(session, deal_id)
    if user_id not in (deal.buyer_id, deal.seller_id):
        raise Forbidden()
    if deal.status not in ("paid", "delivered", "holding"):
        raise BadState()
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise AppError("bad_reason", "Muammoni batafsil yozing")
    deal.status = "disputed"
    deal.dispute_reason = reason[:2000]
    deal.auto_release_at = None
    deal.hold_until = None
    await _system(session, deal.chat_id, "⚖️ Nizo ochildi. Pul muzlatildi, admin ikkala tomonni ko'rib chiqadi.")
    other = deal.seller_id if user_id == deal.buyer_id else deal.buyer_id
    out.user(other, f"⚖️ Bitim #{deal.id} bo'yicha nizo ochildi. Admin bog'lanadi.", webapp_button("Bitimni ochish", f"/deal/{deal.id}"))
    out.admins(f"⚖️ Nizo: bitim #{deal.id} · {fmt(deal.price)}\nSabab: {reason[:500]}", webapp_button("Admin panel", "/admin"), topic="nizo")
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
            await _confirm_or_hold(session, deal, out, "avtomatik tasdiq")
            done += 1
    held = list(await session.scalars(select(Deal.id).where(Deal.status == "holding", Deal.hold_until <= _now()).limit(limit)))
    for deal_id in held:
        deal = await lock_deal(session, deal_id)
        if deal.status == "holding" and deal.hold_until and deal.hold_until <= _now():
            await _complete(session, deal, out, "himoya muddati tugadi")
            done += 1
    return done


async def deadline_tick(session: AsyncSession, out: Outbox, limit: int = 100) -> int:
    """Sotuvchi muddatda ma'lumot bermasa — bitim avtomatik bekor, pul qaytadi, sotuvchiga ogohlantirish (strike).
    Muddatga 3 soat qolganda sotuvchiga eslatma."""
    from app.services import app_settings

    now = _now()
    n = 0
    late = list(await session.scalars(select(Deal.id).where(Deal.status == "paid", Deal.deliver_by <= now).limit(limit)))
    block = int(await app_settings.get_value(session, "strikes_block"))
    for deal_id in late:
        deal = await lock_deal(session, deal_id)
        if deal.status != "paid" or not deal.deliver_by or deal.deliver_by > now:
            continue
        await _refund(session, deal, out, "sotuvchi muddatda ma'lumot bermadi", relist=True)
        seller = await session.scalar(select(User).where(User.id == deal.seller_id).with_for_update().execution_options(populate_existing=True))
        seller.seller_strikes = (seller.seller_strikes or 0) + 1
        out.user(seller.id, f"⚠️ Muddat buzildi ({seller.seller_strikes}/{block}). {block} marta takrorlansa, yangi e'lon qo'sha olmaysiz va "
                            "pul ushlab turish muddati uzayadi.")
        if seller.seller_strikes >= block:
            await session.execute(update(Listing).where(Listing.seller_id == seller.id, Listing.status == "active").values(status="closed"))
            out.admins(f"🚫 Sotuvchi {seller.id} {seller.seller_strikes} marta muddatni buzdi — e'lonlari yopildi.", None, topic="nizo")
        n += 1
    warn = list(await session.scalars(select(Deal.id).where(
        Deal.status == "paid", Deal.deliver_warned.is_(False), Deal.deliver_by <= now + WARN_BEFORE, Deal.deliver_by > now).limit(limit)))
    for deal_id in warn:
        deal = await lock_deal(session, deal_id)
        if deal.status == "paid" and not deal.deliver_warned:
            deal.deliver_warned = True
            out.user(deal.seller_id, f"⏰ «{deal.listing.title}»: akkaunt ma'lumotini yuborishga 3 soatdan kam qoldi. Aks holda bitim bekor bo'ladi.",
                     webapp_button("Bitimni ochish", f"/deal/{deal.id}"))
    return n


def credentials_for(deal: Deal, user_id: int, is_admin: bool = False) -> str | None:
    """Login/parolni faqat xaridor (va admin) ko'radi."""
    if deal.status not in ("delivered", "holding", "completed", "disputed"):
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
    from app.models import User

    seller = await session.get(User, seller_id, with_for_update=True)
    if seller.vip_credit_days >= days:  # Hamkor yoki ball evaziga olingan bepul VIP kunlari
        seller.vip_credit_days -= days
        price = 0
    if price > 0:
        await wallet.debit(session, seller_id, price, "vip", f"vip:{listing_id}:{_now().timestamp()}", ref_type="listing", ref_id=listing_id,
                           note=f"VIP {days} kun")
    start = listing.vip_until if listing.vip_until and listing.vip_until > _now() else _now()
    listing.vip_until = start + timedelta(days=days)
    return listing


# ------------------------------------------------------------------ narx ogohlantirishi
async def price_hint(session: AsyncSession, item: Listing) -> dict | None:
    """Shu o'yin va rank bo'yicha boshqa e'lonlar narxi mediana. Juda arzon e'lon — firibgarlik belgisi."""
    rows = list(await session.scalars(
        select(Listing.price).where(Listing.game == item.game, Listing.rank == item.rank, Listing.id != item.id,
                                    Listing.status.in_(("active", "reserved", "sold"))).limit(200)))
    if len(rows) < 3:
        return None
    rows.sort()
    median = rows[len(rows) // 2]
    ratio = item.price / median if median else 1
    return {"median": median, "level": "low" if ratio < 0.4 else ("high" if ratio > 2.5 else "fair")}
