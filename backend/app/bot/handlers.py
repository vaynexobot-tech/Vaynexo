"""Bot: Mini App'ni ochish, admin uchun bank xabarini qabul qilish, boosterlar guruhi."""

import logging
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import (
    CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, InlineQuery, InlineQueryResultArticle, InlineQueryResultsButton,
    InputTextMessageContent, Message, WebAppInfo,
)
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.errors import AppError
from app.models import BoostOrder, User
from app.queue import enqueue
from app.security import decrypt
from app.services import account, notify, p2p
from app.bot.instance import get_bot
from app.services import services as svc
from app.services.notify import Outbox, fmt

log = logging.getLogger(__name__)
router = Router()


def open_app_kb(text: str = "🎮 VAYNEXO ni ochish", path: str = "") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=text, web_app=WebAppInfo(url=settings.webapp_url.rstrip("/") + path))
    ]])


def menu_kb() -> InlineKeyboardMarkup:
    """/start menyusi: bitta tugma — ilovani ochish."""
    return open_app_kb()


async def set_commands(bot) -> None:
    """Bot menyusidagi buyruqlar ro'yxati (chap pastdagi «Menu»)."""
    from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Bosh menyu"),
            BotCommand(command="arena", description="Arena: viktorina, turnir, reyting"),
            BotCommand(command="qahramonlar", description="MLBB qahramonlar: skill, buyum, counter"),
            BotCommand(command="donat", description="Almaz donat"),
            BotCommand(command="hamyon", description="Hamyon va balans"),
            BotCommand(command="help", description="Yordam"),
        ], scope=BotCommandScopeAllPrivateChats())
    except Exception:  # noqa: BLE001
        log.exception("Bot buyruqlari o'rnatilmadi")


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


async def ensure_user(tg_user, ref: int | None = None) -> User:
    async with SessionLocal() as session, session.begin():
        user = await session.get(User, tg_user.id)
        if user is None:
            if ref and (ref == tg_user.id or not await session.get(User, ref)):
                ref = None
            user = User(
                id=tg_user.id, username=tg_user.username, first_name=(tg_user.first_name or "")[:128],
                lang="ru" if (tg_user.language_code or "").startswith("ru") else "uz",
                referrer_id=ref, is_admin=is_admin(tg_user.id),
            )
            session.add(user)
            if ref:
                from app.services import arena

                await session.flush()
                await arena.bump(session, ref, "invite")
        elif user.username != tg_user.username:
            user.username = tg_user.username
    return user


DEEP_PAGES = {"admin": "Admin panel", "listing": "E'lonni ochish", "deal": "Bitimni ochish", "chat": "Chatni ochish",
              "boost": "Buyurtmani ochish", "rental": "Ijarani ochish", "arena": "Turnirni ochish", "wallet": "Hamyonni ochish",
              "partner": "Hamkor", "shop": "Do'kon", "plus": "VAYNEXO Plus", "savings": "Jamg'arma", "pro": "Pro bilan o'yna", "streamer": "Striminer paneli", "booster": "Booster", "rent": "Ijara", "history": "Tarix", "my-listings": "E'lonlarim"}


def deep_link_path(arg: str | None) -> tuple[str, str] | None:
    """Kanal/guruh tugmasi: t.me/bot?start=listing_15 → (/listing/15, «E'lonni ochish»)."""
    sd = re.fullmatch(r"(split|duel)_([a-z0-9]{6,12})", arg or "")
    if sd:
        return f"/{sd.group(1)}/{sd.group(2)}", "🤝 Birgalikda to'lov" if sd.group(1) == "split" else "⚔️ Draft Jang"
    st = re.fullmatch(r"stream_([a-z0-9_]{3,24})", arg or "")
    if st:
        return f"/s/{st.group(1)}", "🎁 Donat yuborish"
    d = re.fullmatch(r"donate_([A-Za-z0-9-]{1,60})", arg or "")  # inline qidiruvdan: donate_ML, donate_pubg-mobile
    if d:
        return f"/donate/{d.group(1)}", "💎 Donat qilish"
    m = re.fullmatch(r"([a-z-]+)(?:_(\d+))?", arg or "")
    if not m or m.group(1) not in DEEP_PAGES:
        return None
    return "/" + m.group(1) + (f"/{m.group(2)}" if m.group(2) else ""), DEEP_PAGES[m.group(1)]


@router.message(CommandStart(), F.chat.type == "private")
async def start(message: Message, command: CommandObject):
    from app.services import launch

    if not await launch.allowed(message.from_user.id):
        await ensure_user(message.from_user, None)  # ro'yxatga olamiz, ochilganda xabar berish mumkin
        await message.answer(await launch.soon_text())
        return
    ref = None
    if command.args and command.args.startswith("ref_") and command.args[4:].isdigit():
        ref = int(command.args[4:])
    await ensure_user(message.from_user, ref)
    if command.args and command.args.startswith("shop_"):
        from sqlalchemy import select

        from app.models import Shop
        from app.services import shops

        async with SessionLocal() as session, session.begin():
            u = await session.get(User, message.from_user.id)
            await shops.attach(session, u, command.args[5:])
            shop = await session.get(Shop, u.shop_id) if u.shop_id else await session.scalar(select(Shop).where(Shop.slug == shops.clean_slug(command.args[5:])))
        if shop:
            await message.answer(f"🏪 {shop.name}\n{shop.tagline}\n\n💎 Donat, Premium va Stars shu yerda — tez va xavfsiz." if shop.tagline
                                 else f"🏪 {shop.name}\n\n💎 Donat, Premium va Stars shu yerda — tez va xavfsiz.",
                                 reply_markup=open_app_kb("🏪 Do'konni ochish", "/"))
            return
    deep = deep_link_path(command.args)
    if deep and not (deep[0] == "/admin" and not is_admin(message.from_user.id)):
        await message.answer("👇 Ochish uchun tugmani bosing", reply_markup=open_app_kb(f"📲 {deep[1]}", deep[0]))
        return
    await message.answer(await launch.text("text_start"), reply_markup=menu_kb())


async def _quick(message: Message, text: str, btn: str, path: str) -> None:
    from app.services import launch

    if not await launch.allowed(message.from_user.id):
        await message.answer(await launch.soon_text())
        return
    await message.answer(text, reply_markup=open_app_kb(btn, path))


@router.message(Command("arena"), F.chat.type == "private")
async def arena_cmd(message: Message):
    await _quick(message, "🏆 Arena: bugungi «Qahramonni top» viktorinasi, haftaning qahramoni ovozi, turnirlar va reyting.",
                 "🏆 Arenani ochish", "/arena")


@router.message(Command("qahramonlar"), F.chat.type == "private")
async def heroes_cmd(message: Message):
    await _quick(message, "📖 MLBB qahramonlari: skillar, tavsiya buyumlar va counter-pick (rasmiy ma'lumot).",
                 "📖 Qahramonlar", "/heroes")


@router.message(Command("donat"), F.chat.type == "private")
async def donat_cmd(message: Message):
    await _quick(message, "💎 O'yinni tanlang, ID kiriting — donat bir necha daqiqada tushadi.", "💎 Donat", "/")


@router.message(Command("hamyon"), F.chat.type == "private")
async def wallet_cmd(message: Message):
    await _quick(message, "💳 Hamyon: balans, to'ldirish va promo-kod.", "💳 Hamyonni ochish", "/wallet")


@router.message(Command("ochish"))
async def open_all(message: Message):
    """Admin: ilovani hamma uchun ochadi."""
    if is_admin(message.from_user.id):
        from app.services import launch

        await launch.set_open(True)
        await message.answer("✅ Ilova hamma uchun ochildi. Yopish: /yopish")


@router.message(Command("yopish"))
async def close_all(message: Message):
    """Admin: ilovani yopadi (faqat adminlar kira oladi, qolganlarga «Tez kunda»)."""
    if is_admin(message.from_user.id):
        from app.services import launch

        await launch.set_open(False)
        await message.answer("🔒 Ilova yopildi: faqat adminlar kira oladi, qolganlarga «Tez kunda» chiqadi. Ochish: /ochish")


@router.message(Command("ruxsat"))
async def guest_add(message: Message, command: CommandObject):
    """Admin: yopiq rejimda ma'lum odamga ruxsat. /ruxsat 123456789 — qo'shish; /ruxsat — ro'yxat."""
    if not is_admin(message.from_user.id):
        return
    from app.services import launch

    ids = await launch.guests()
    arg = (command.args or "").strip()
    if not arg:
        await message.answer("👥 Ruxsat berilganlar: " + (", ".join(str(i) for i in sorted(ids)) or "yo'q")
                             + "\n\nQo'shish: /ruxsat <ID>\nOlib tashlash: /ruxsatyoq <ID>\nID ni odam @userinfobot dan bilib oladi.")
        return
    if not arg.isdigit():
        await message.answer("ID faqat raqamlardan iborat bo'lsin. Masalan: /ruxsat 123456789")
        return
    ids.add(int(arg))
    await launch.set_guests(ids)
    await message.answer(f"✅ {arg} ga ruxsat berildi (jami {len(ids)}). Endi u /start bosib ilovaga kira oladi.")


@router.message(Command("ruxsatyoq"))
async def guest_remove(message: Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    from app.services import launch

    arg = (command.args or "").strip()
    ids = await launch.guests()
    if not arg.isdigit() or int(arg) not in ids:
        await message.answer("Bunday ID ro'yxatda yo'q. Ro'yxat: /ruxsat")
        return
    ids.discard(int(arg))
    await launch.set_guests(ids)
    await message.answer(f"🚫 {arg} dan ruxsat olib tashlandi.")


@router.inline_query()
async def inline_search(q: InlineQuery):
    """Istalgan chatda «@bot 86», «@bot pubg 660» — paketlar va narxlar. Bosilganda chatga e'lon yuboriladi."""
    from app.services import inline_search as srch
    from app.services import launch

    if not await launch.allowed(q.from_user.id):
        await q.answer([], cache_time=60, is_personal=True,
                       button=InlineQueryResultsButton(text="🚀 VAYNEXO tez kunda ochiladi", start_parameter="inline"))
        return
    async with SessionLocal() as s:
        rows = await srch.search(s, q.query)
    results = []
    for r in rows:
        kb = None
        if settings.bot_username:
            kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
                text="💎 Sotib olish", url=f"https://t.me/{settings.bot_username}?start=donate_{r['game']}")]])
        price = notify.fmt(r["price"])
        how = "🎁 Kod darhol beriladi" if r["voucher"] else "⚡ 1–5 daqiqada ID'ga tushadi"
        results.append(InlineQueryResultArticle(
            id=f"p{r['id']}", title=f"{r['name']} · {r['game_name']}", description=f"{price} so'm · {how}",
            thumbnail_url=r["logo"],
            input_message_content=InputTextMessageContent(
                message_text=f"💎 {r['game_name']} — {r['name']}\n💰 Narxi: {price} so'm\n{how}, kafolat bilan\n\nVAYNEXO orqali sotib oling 👇"),
            reply_markup=kb))
    button = InlineQueryResultsButton(text="🎮 VAYNEXO ni ochish", start_parameter="inline")
    if not results:
        button = InlineQueryResultsButton(text="Topilmadi — barcha o'yinlarni ko'rish", start_parameter="inline")
    await q.answer(results, cache_time=60, is_personal=False, button=button)


@router.message(Command("help"), F.chat.type == "private")
async def help_cmd(message: Message):
    from app.services import launch

    if not await launch.allowed(message.from_user.id):
        await message.answer(await launch.soon_text())
        return
    await message.answer("Savollar bo'yicha: @vaynexo_support\nIlovani ochish:", reply_markup=open_app_kb())


async def is_booster(bot, user_id: int) -> bool:
    """Booster — boosterlar guruhi a'zosi (yoki admin)."""
    if is_admin(user_id):
        return True
    group = await notify.get_booster_group()
    if not group:
        return False
    try:
        m = await bot.get_chat_member(group, user_id)
        return m.status in ("member", "administrator", "creator", "restricted")
    except Exception:
        return False


@router.message(Command("administ"), F.chat.type == "private")
async def administ(message: Message):
    """Yashirin admin buyrug'i: tezkor vazifalar va statistika."""
    if not is_admin(message.from_user.id):
        return
    from app.models import Deal, Listing, PartnerVideo, Rental, RentListing, TgOrder, Withdrawal

    async with SessionLocal() as session:
        cnt = lambda q: session.scalar(select(func.count()).select_from(q))  # noqa: E731
        users = await session.scalar(select(func.count()).select_from(User))
        rows = [
            ("🆕 E'lonlar moderatsiyada", await cnt(select(Listing).where(Listing.status == "moderation").subquery())),
            ("🔑 Ijara e'lonlari", await cnt(select(RentListing).where(RentListing.status == "moderation").subquery())),
            ("🪪 KYC so'rovlari", await cnt(select(User).where(User.kyc_status == "pending").subquery())),
            ("🎬 Hamkor videolari", await cnt(select(PartnerVideo).where(PartnerVideo.status == "pending").subquery())),
            ("💸 Pul yechish", await cnt(select(Withdrawal).where(Withdrawal.status == "pending").subquery())),
            ("⭐️ TG buyurtmalar", await cnt(select(TgOrder).where(TgOrder.status.in_(("paid", "processing"))).subquery())),
            ("⚖️ Nizolar", await cnt(select(Deal).where(Deal.status == "disputed").subquery())
             + await cnt(select(Rental).where(Rental.status == "disputed").subquery())),
            ("⚠️ Biriktirilmagan kirimlar", await p2p.unmatched_count(session)),
            ("🚀 Booster kutayotgan boost", await cnt(select(BoostOrder).where(BoostOrder.status == "searching").subquery())),
        ]
    text = f"🛠 VAYNEXO admin\n👥 Foydalanuvchilar: {users}\n\n" + "\n".join(f"{n}: {c}" for n, c in rows)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Mobil (shu yerda)", web_app=WebAppInfo(url=settings.webapp_url.rstrip("/") + "/admin"))],
        [InlineKeyboardButton(text="💻 Web (kompyuter) havolasi", callback_data="webadmin")],
    ])
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "webadmin")
async def web_admin_link(call: CallbackQuery):
    """Admin: kompyuter brauzerida ochiladigan 12 soatlik shaxsiy havola."""
    if not is_admin(call.from_user.id):
        await call.answer()
        return
    from app.security import WEB_TOKEN_TTL, make_web_token

    url = f"{settings.webapp_url.rstrip('/')}/admin?web=1#wt={make_web_token(call.from_user.id)}"
    await call.message.answer(
        f"💻 Admin panel (kompyuter uchun), {WEB_TOKEN_TTL // 3600} soat amal qiladi.\n"
        "Havolani hech kimga bermang — u orqali admin sifatida kiriladi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💻 Brauzerda ochish", url=url)]]),
    )
    await call.answer()


@router.message(Command("booster"), F.chat.type == "private")
async def booster_cmd(message: Message):
    """Yashirin booster buyrug'i: yangi buyurtmalar va o'z buyurtmalarim."""
    if not await is_booster(message.bot, message.from_user.id):
        return
    await get_share_pct()
    async with SessionLocal() as session:
        mine = list(await session.scalars(select(BoostOrder).where(
            BoostOrder.booster_id == message.from_user.id, BoostOrder.status.in_(("accepted", "in_progress", "finished"))
        ).order_by(BoostOrder.id)))
        new = list(await session.scalars(select(BoostOrder).where(BoostOrder.status == "searching").order_by(BoostOrder.id).limit(10)))
    if not mine and not new:
        await message.answer("Hozircha buyurtma yo'q. Yangi buyurtmalar boosterlar guruhiga tushadi.")
        return
    for o in mine:
        extra = f"\nProgress: {o.progress_stars}/{o.stars}★\nYangilash: /progress {o.id} <olingan yulduz> [win-rate]"
        await message.answer("📌 Sizning buyurtmangiz\n" + boost_post_text(o) + extra, reply_markup=booster_dm_kb(o))
    for o in new:
        await message.answer(boost_post_text(o), reply_markup=boost_post_kb(o))


@router.message(Command("progress"), F.chat.type == "private")
async def progress_cmd(message: Message, command: CommandObject):
    """/progress <buyurtma> <olingan yulduz> [win-rate] — mijozga jonli progress yuboriladi."""
    parts = (command.args or "").split()
    if len(parts) < 2 or not parts[0].lstrip("#").isdigit() or not parts[1].isdigit():
        await message.answer("Foydalanish: /progress 1043 12 74\n(buyurtma raqami, olingan yulduz, win-rate % — ixtiyoriy)")
        return
    winrate = int(parts[2].rstrip("%")) if len(parts) > 2 and parts[2].rstrip("%").isdigit() else None
    out = Outbox()
    try:
        async with SessionLocal() as session, session.begin():
            o = await svc.boost_report_progress(session, int(parts[0].lstrip("#")), message.from_user.id, int(parts[1]), winrate, out)
    except AppError as e:
        await message.answer(f"❌ {e.message}")
        return
    await out.flush()
    await message.answer(f"✅ Yuborildi: {o.progress_stars}/{o.stars}★ — mijozga xabar ketdi.")


@router.message(Command("kyc_guruh"), F.chat.type.in_({"group", "supergroup"}))
async def kyc_here(message: Message):
    """Admin guruhda yozadi: identifikatsiya so'rovlari shu guruhga keladi."""
    if not is_admin(message.from_user.id):
        return
    await account.set_kyc_chat(message.chat.id)
    await message.answer("✅ Identifikatsiya so'rovlari endi shu guruhga keladi.\n"
                         "⚠️ Guruhda pasport rasmlari bo'ladi — faqat ishonchli adminlarni qo'shing.\nBekor qilish: /kyc_ochir")


async def _channel_owned_by_admin(chat_id: int) -> bool:
    """Kanal buyrug'ini kim yozganini bilib bo'lmaydi — kanal adminlari orasida bizning admin bo'lishi shart.
    Aks holda begona odam o'z kanaliga botni qo'shib, admin xabarlarini (va pasport rasmlarini) o'ziga burib oladi."""
    try:
        admins = await get_bot().get_chat_administrators(chat_id)
    except Exception:  # noqa: BLE001
        return False
    return any(a.user.id in settings.admin_ids for a in admins)


@router.channel_post(Command("kyc_guruh"))
async def kyc_here_channel(post: Message):
    if not await _channel_owned_by_admin(post.chat.id):
        await post.answer("⛔ Bu kanalda bot admini (ADMIN_IDS) kanal admini emas.")
        return
    await account.set_kyc_chat(post.chat.id)
    await post.answer("✅ Identifikatsiya so'rovlari endi shu kanalga keladi. Bekor qilish: /kyc_ochir")


@router.message(Command("kyc_ochir"))
async def kyc_off(message: Message):
    if not is_admin(message.from_user.id):
        return
    await account.set_kyc_chat(None)
    await message.answer("Identifikatsiya so'rovlari yana adminlarga shaxsiy xabarda keladi.")


@router.channel_post(Command("kyc_ochir"))
async def kyc_off_channel(post: Message):
    if not await _channel_owned_by_admin(post.chat.id):
        return
    await account.set_kyc_chat(None)
    await post.answer("Identifikatsiya so'rovlari yana adminlarga shaxsiy xabarda keladi.")


# ------------------------------------------------------------------ admin xabarlari kanali
ADMIN_CHAT_TEXT = ("✅ Admin xabarlari endi shu yerga keladi: yangi e'lonlar (moderatsiya), to'lovlar, pul yechish, "
                   "nizolar, bank kirimlari, identifikatsiya va h.k.\n"
                   "Tugmalarni faqat ADMIN_IDS dagi adminlar bosa oladi. Bekor qilish: /admin_kanal_ochir")


@router.message(Command("admin_kanal"), F.chat.type.in_({"group", "supergroup"}))
async def admin_chat_here(message: Message):
    if not is_admin(message.from_user.id):
        return
    await notify.set_admin_chat(message.chat.id)
    await message.answer(ADMIN_CHAT_TEXT)


@router.channel_post(Command("admin_kanal"))
async def admin_chat_here_channel(post: Message):
    if not await _channel_owned_by_admin(post.chat.id):
        await post.answer("⛔ Bu kanalda bot admini (ADMIN_IDS) kanal admini emas.")
        return
    await notify.set_admin_chat(post.chat.id)
    await post.answer(ADMIN_CHAT_TEXT)


@router.message(Command("admin_kanal_ochir"))
async def admin_chat_off(message: Message):
    if not is_admin(message.from_user.id):
        return
    await notify.set_admin_chat(None)
    await message.answer("Admin xabarlari yana shaxsiy xabarda keladi.")


@router.channel_post(Command("admin_kanal_ochir"))
async def admin_chat_off_channel(post: Message):
    if not await _channel_owned_by_admin(post.chat.id):
        return
    await notify.set_admin_chat(None)
    await post.answer("Admin xabarlari yana shaxsiy xabarda keladi.")


def _topics_kb(bound: dict) -> InlineKeyboardMarkup:
    rows, row = [], []
    for k, v in notify.TOPICS.items():
        row.append(InlineKeyboardButton(text=("✅ " if k in bound else "") + v, callback_data=f"mavzu:{k}"))
        if len(row) == 1:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


ELON_TEXT = ("✅ Bu kanal endi «Account savdo» e'lonlari kanali.\n\n"
             "• Admin tasdiqlagan har bir e'lon shu yerga post bo'ladi («🛒 Sotib olish» tugmasi bilan)\n"
             "• Xaridor to'lasa — «BAND», sotilsa — «SOTILDI» ga o'zgaradi, o'chirilsa post ham o'chadi\n"
             "• Hozirgi faol e'lonlar ham daqiqasiga 5 tadan chiqariladi\n\nO'chirish: /elon_kanal_ochir")


@router.channel_post(Command("elon_kanal"))
async def listing_channel_here(post: Message):
    from app.services import channel

    if not await _channel_owned_by_admin(post.chat.id):
        await post.answer("⛔ Bu kanalda bot admini (ADMIN_IDS) kanal admini emas.")
        return
    await channel.set_channel(post.chat.id)
    await post.answer(ELON_TEXT)


@router.message(Command("elon_kanal"), F.chat.type.in_({"group", "supergroup"}))
async def listing_channel_group(message: Message):
    from app.services import channel

    if not is_admin(message.from_user.id):
        return
    await channel.set_channel(message.chat.id)
    await message.answer(ELON_TEXT.replace("kanal", "guruh"))


@router.channel_post(Command("elon_kanal_ochir"))
async def listing_channel_off_ch(post: Message):
    from app.services import channel

    if await _channel_owned_by_admin(post.chat.id):
        await channel.set_channel(None)
        await post.answer("E'lonlar kanali uzildi. Yangi e'lonlar endi bu yerga chiqmaydi.")


@router.message(Command("elon_kanal_ochir"))
async def listing_channel_off(message: Message):
    from app.services import channel

    if is_admin(message.from_user.id):
        await channel.set_channel(None)
        await message.answer("E'lonlar kanali uzildi.")


@router.message(Command("booster_guruh"), F.chat.type.in_({"group", "supergroup"}))
async def booster_group_here(message: Message):
    """Admin guruhda yozadi: yangi boost buyurtmalar shu guruhga tushadi, a'zolari booster hisoblanadi."""
    if not is_admin(message.from_user.id):
        return
    await notify.set_booster_group(message.chat.id)
    await message.answer(
        "✅ Bu guruh endi boosterlar guruhi.\n\n"
        "• Yangi boost buyurtmalar shu yerga tushadi — booster «Olish» tugmasini bosadi\n"
        "• Guruh a'zolari booster hisoblanadi (botda /booster buyrug'i ochiladi)\n"
        "• Faqat ishonchli boosterlarni qo'shing\n\nO'chirish: /booster_guruh_ochir")


@router.message(Command("booster_guruh_ochir"))
async def booster_group_off(message: Message):
    if not is_admin(message.from_user.id):
        return
    await notify.set_booster_group(None)
    await message.answer("Boosterlar guruhi uzildi. Yangi boost buyurtmalar admin guruhiga («boost» mavzusi) tushadi.")


@router.message(Command("mavzu_tozalash"))
async def topics_reset(message: Message):
    """Hamma mavzu ulanishlarini o'chiradi — keyin /mavzu bilan qaytadan ulanadi."""
    if not is_admin(message.from_user.id):
        return
    await notify.reset_admin_routing()
    await message.answer("🧹 Hamma mavzu ulanishlari o'chirildi. Endi har bir mavzuda /mavzu yozib qaytadan ulang.")


@router.message(Command(re.compile(r"mavzu(_\w+)?")), F.chat.type.in_({"group", "supergroup"}))
async def topic_here(message: Message, command: CommandObject):
    """Guruh mavzusida /mavzu yoziladi → tugmalardan birini bosasiz → shu turdagi xabarlar shu mavzuga keladi.
    Qo'lda ham bo'ladi: /mavzu nizo yoki /mavzu_nizo."""
    if not is_admin(message.from_user.id):
        return
    raw = (command.command[6:] if command.command.startswith("mavzu_") else (command.args or "")).strip().lower()
    key = raw.split()[0].strip("-—:") if raw else ""
    thread = message.message_thread_id if message.is_topic_message else None
    if key.endswith("_ochir") and key[:-6] in notify.TOPICS:
        await notify.set_topic(key[:-6], None)
        await message.answer(f"«{notify.TOPICS[key[:-6]]}» uzildi.")
        return
    if key in notify.TOPICS:
        await notify.set_topic(key, message.chat.id, thread)
        await message.answer(f"✅ Endi «{notify.TOPICS[key]}» shu mavzuga keladi.")
        return
    await message.answer("Bu mavzuga qaysi xabarlar kelsin? Tugmani bosing 👇", reply_markup=_topics_kb(await notify.get_topics()))


@router.callback_query(F.data.startswith("mavzu:"))
async def topic_pick(cb: CallbackQuery):
    if cb.from_user.id not in settings.admin_ids:
        await cb.answer("Faqat admin uchun", show_alert=True)
        return
    key = cb.data.split(":", 1)[1]
    if key not in notify.TOPICS or not cb.message:
        return
    msg = cb.message
    thread = msg.message_thread_id if msg.is_topic_message else None
    await notify.set_topic(key, msg.chat.id, thread)
    await cb.answer("Saqlandi ✅")
    try:
        await msg.edit_text(f"✅ Endi «{notify.TOPICS[key]}» shu mavzuga keladi.\nO'zgartirish: /mavzu")
    except Exception:  # noqa: BLE001
        pass


@router.message(Command("stats"), F.chat.type == "private")
async def stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    async with SessionLocal() as session:
        users = await session.scalar(select(func.count()).select_from(User))
        unmatched = await p2p.unmatched_count(session)
    await message.answer(f"👥 Foydalanuvchilar: {users}\n⚠️ Biriktirilmagan kirimlar: {unmatched}",
                         reply_markup=open_app_kb("Admin panel", "/admin"))


@router.message(Command("id"))
async def chat_id(message: Message):
    """Guruh ID sini bilish uchun (BOOSTER_GROUP_ID / ADMIN_CHAT_ID)."""
    await message.answer(f"Chat ID: {message.chat.id}")


@router.message(F.chat.type == "private", F.text | F.caption)
async def admin_bank_forward(message: Message):
    """Admin bank bildirishnomasini (Humo/Uzcard bot, SMS) botga forward qiladi — kirim avtomatik topiladi."""
    if not is_admin(message.from_user.id):
        from app.services import launch

        if await launch.allowed(message.from_user.id):
            await message.answer("Ilovani ochish uchun tugmani bosing 👇", reply_markup=open_app_kb())
        else:
            await message.answer(await launch.soon_text())
        return
    text = message.text or message.caption or ""
    amount = p2p.parse_bank_message(text)
    if not amount:
        await message.answer("Bu xabardan kirim summasi topilmadi.")
        return
    origin = message.forward_origin
    origin_date = getattr(origin, "date", None) or message.date
    out = Outbox()
    async with SessionLocal() as session, session.begin():
        inc = await p2p.register_incoming(
            session, amount, "bot_forward", out, raw_text=text, external_id=f"fwd:{origin_date.isoformat()}:{amount}:{text[:200]}"
        )
    await out.flush()
    if inc is None:
        await message.answer(f"ℹ️ Bu kirim oldin qayd etilgan ({fmt(amount)}).")
    elif inc.status == "matched":
        await message.answer(f"✅ {fmt(amount)} — so'rov #{inc.topup_id} ga biriktirildi, balans to'ldirildi.")
    else:
        await message.answer(f"⚠️ {fmt(amount)} — mos so'rov topilmadi. Admin paneldan biriktiring.",
                             reply_markup=open_app_kb("Admin panel", "/admin"))


# ------------------------------------------------------------------ boosterlar guruhi
_share_pct = 70  # admin paneldagi «Booster ulushi»; get_share_pct() yangilaydi


async def get_share_pct() -> int:
    global _share_pct
    from app.services import app_settings

    try:
        async with SessionLocal() as session:
            _share_pct = int(await app_settings.get_value(session, "booster_share_percent"))
    except Exception:
        log.debug("booster ulushini o'qib bo'lmadi", exc_info=True)
    return _share_pct


def boost_post_text(o: BoostOrder) -> str:
    status = {"searching": "🟢 YANGI", "accepted": "🟡 Olingan", "in_progress": "🔵 Jarayonda", "finished": "🏁 Tugatildi",
              "done": "✅ Yakunlandi", "refunded": "⛔️ Bekor qilindi", "disputed": "⚖️ Nizo"}.get(o.status, o.status)
    lines = [
        f"Buyurtma #{o.id} · {status}",
        f"Xizmat: Rank boost ({o.game})",
        f"Rank: {o.current_rank} → {o.target_rank}",
        f"Yulduz: {o.stars}",
        f"Liniya: {o.lane or 'Ixtiyoriy'}",
        f"Kirish: {o.login_method}",
        f"Booster ulushi: {fmt(o.price * _share_pct // 100)}",
    ]
    if o.note:
        lines.append(f"Izoh: {o.note}")
    if o.booster_name:
        lines.append(f"Booster: {o.booster_name}")
    return "\n".join(lines)


def boost_post_kb(o: BoostOrder) -> InlineKeyboardMarkup | None:
    if o.status != "searching":
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"boost:accept:{o.id}")]])


def booster_dm_kb(o: BoostOrder) -> InlineKeyboardMarkup | None:
    if o.status == "accepted":
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🚀 Ishni boshladim", callback_data=f"boost:start:{o.id}")]])
    if o.status == "in_progress":
        return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🏁 Tugatdim", callback_data=f"boost:finish:{o.id}")]])
    return None


@router.callback_query(F.data.startswith("boost:"))
async def boost_callback(cb: CallbackQuery):
    _, action, oid = cb.data.split(":")
    order_id = int(oid)
    booster = await ensure_user(cb.from_user)
    out = Outbox()
    try:
        async with SessionLocal() as session, session.begin():
            if action == "accept":
                order = await svc.boost_accept(session, order_id, booster, out)
            else:
                order = await svc.boost_progress(session, order_id, booster.id, action, out)
            creds = decrypt(order.credentials_enc) if action == "accept" else None
    except AppError as e:
        await cb.answer(e.message, show_alert=True)
        return
    await out.flush()
    await get_share_pct()
    if action == "accept":
        dm = boost_post_text(order) + (f"\n\n🔐 Kirish ma'lumotlari:\n{creds}" if creds else
                                       "\n\nMijoz bilan bog'lanish uchun admin bilan aloqa qiling.")
        try:
            await cb.bot.send_message(booster.id, dm, reply_markup=booster_dm_kb(order))
            await cb.answer("Buyurtma sizniki ✅ Tafsilotlar shaxsiy xabarda.")
        except Exception:
            log.warning("Boosterga DM yuborilmadi (botni /start qilmagan bo'lishi mumkin)")
            await cb.answer("Buyurtma sizniki, lekin shaxsiy xabar yuborilmadi: botga /start yozing va adminga murojaat qiling.", show_alert=True)
            out.admins(f"⚠️ Booster {booster.id} buyurtma #{order_id} ni oldi, lekin DM yuborilmadi.", topic="boost")
            await out.flush()
    else:
        await cb.answer("Bajarildi ✅")
        try:
            await cb.message.edit_reply_markup(reply_markup=booster_dm_kb(order))
        except Exception:
            pass
    await enqueue("update_boost_post", order_id)


@router.callback_query(F.data.startswith("kyc:"))
async def kyc_callback(cb: CallbackQuery):
    """Admin identifikatsiya so'rovini tasdiqlaydi yoki rad etadi."""
    if cb.from_user.id not in settings.admin_ids:
        await cb.answer("Faqat admin uchun", show_alert=True)
        return
    _, action, uid = cb.data.split(":")
    out = Outbox()
    try:
        async with SessionLocal() as session:
            await account.kyc_resolve(session, int(uid), action == "ok", None, out)
    except AppError as e:
        await cb.answer(e.message, show_alert=True)
        return
    await out.flush()
    from app.services import audit

    await audit.write(cb.from_user.id, "Identifikatsiya (bot)", "tasdiqlandi" if action == "ok" else "rad etildi", None, int(uid))
    await cb.answer("Tasdiqlandi ✅" if action == "ok" else "Rad etildi")
    try:
        await cb.message.edit_text(cb.message.text + ("\n\n✅ Tasdiqlandi" if action == "ok" else "\n\n❌ Rad etildi"))
    except Exception:
        pass


@router.callback_query(F.data.startswith("donate:"))
async def donate_callback(cb: CallbackQuery):
    """Admin qo'lda bajarilgan donatni tasdiqlaydi yoki pulni qaytaradi."""
    if cb.from_user.id not in settings.admin_ids:
        await cb.answer("Faqat admin uchun", show_alert=True)
        return
    from app.services import donate as donate_svc

    _, action, oid = cb.data.split(":")
    out = Outbox()
    try:
        async with SessionLocal() as session, session.begin():
            await donate_svc.admin_resolve(session, int(oid), action, out)
    except AppError as e:
        await cb.answer(e.message, show_alert=True)
        return
    await out.flush()
    from app.services import audit

    await audit.write(cb.from_user.id, "Donat (bot)", f"buyurtma #{oid}: " + ("bajarildi" if action == "done" else "pul qaytarildi"))
    who = cb.from_user.username or cb.from_user.first_name
    mark = f"\n\n✅ Bajarildi ({who})" if action == "done" else f"\n\n↩️ Pul qaytarildi ({who})"
    await cb.answer("Bajarildi ✅" if action == "done" else "Pul qaytarildi")
    try:
        await cb.message.edit_text((cb.message.text or "") + mark)
    except Exception:  # noqa: BLE001
        pass


@router.callback_query(F.data.startswith("topup:"))
async def topup_callback(cb: CallbackQuery):
    """Admin «To'ladim» so'rovini tasdiqlaydi yoki rad etadi."""
    if cb.from_user.id not in settings.admin_ids:
        await cb.answer("Faqat admin uchun", show_alert=True)
        return
    _, action, tid = cb.data.split(":")
    out = Outbox()
    try:
        async with SessionLocal() as session, session.begin():
            if action == "ok":
                await p2p.admin_confirm(session, int(tid), out)
            else:
                await p2p.admin_reject(session, int(tid), None, out)
    except AppError as e:
        await cb.answer(e.message, show_alert=True)
        return
    await out.flush()
    from app.services import audit

    await audit.write(cb.from_user.id, "«To'ladim» (bot)", f"so'rov #{tid}: " + ("tasdiqlandi" if action == "ok" else "rad etildi"))
    mark = "\n\n✅ Tasdiqlandi — balans to'ldirildi" if action == "ok" else "\n\n❌ Rad etildi"
    await cb.answer("Tasdiqlandi ✅" if action == "ok" else "Rad etildi")
    try:
        if cb.message.photo:
            await cb.message.edit_caption(caption=(cb.message.caption or "") + mark)
        else:
            await cb.message.edit_text((cb.message.text or "") + mark)
    except Exception:
        pass
