"""Admin paneldan o'zgartiriladigan sozlamalar (bazada saqlanadi).

Qiymat bazada bo'lmasa — boshlang'ich qiymat (yoki config/.env dagisi) ishlatiladi.
Turlari: money (so'm), percent (%), choice (ro'yxatdan bittasi).
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError
from app.models import AppSetting


@dataclass(frozen=True)
class Spec:
    kind: str  # money | percent | choice
    default: object  # None -> config dagi shu nomli qiymat
    label: str
    group: str
    lo: int = 0
    hi: int = 100_000_000
    choices: dict[str, str] = field(default_factory=dict)
    show_if: tuple[str, str] | None = None  # admin panelda faqat boshqa sozlama shu qiymatda bo'lsa ko'rinadi


SCHEMA: dict[str, Spec] = {
    # Referal
    "referral_bonus": Spec("money", None, "Taklif bonusi (so'm). 0 — o'chiq", "Referal", 0, 10_000_000),
    "referral_min_topup": Spec("money", 10_000, "Bonus uchun do'stning eng kam to'ldirishi (so'm)", "Referal", 1_000),
    # Hamyon
    "topup_max_silver": Spec("money", 20_000_000, "Bir martalik to'ldirish limiti — Silver (so'm)", "Hamyon", 1_000, 1_000_000_000),
    "topup_timeout_minutes": Spec("money", 10, "To'lov taymeri (daqiqa)", "Hamyon", 3, 120),
    "topup_review_after_minutes": Spec("money", 15, "«To'ladim» bosilib, bank xabari kelmasa — necha daqiqadan keyin adminga xabar",
                                       "Hamyon", 1, 1440),
    # KYC
    "kyc_marketplace": Spec("choice", "on", "Account savdo uchun identifikatsiya", "Identifikatsiya (KYC)",
                            choices={"on": "Majburiy", "off": "Ixtiyoriy"}),
    "kyc_withdraw": Spec("choice", "on", "Pul yechish uchun identifikatsiya (komissiya, savdo, striminer, Pro daromadi)", "Identifikatsiya (KYC)",
                         choices={"on": "Majburiy", "off": "Ixtiyoriy"}),
    "kyc_rental": Spec("choice", "on", "Account ijara uchun identifikatsiya", "Identifikatsiya (KYC)",
                       choices={"on": "Majburiy", "off": "Ixtiyoriy"}),
    # Savdo
    "garant_fee_percent": Spec("percent", 0, "Garant xizmat haqi — sotuvchidan (%)", "Account savdo", 0, 50),
    "escrow_release_days": Spec("money", 3, "Xaridor javob bermasa, necha kundan keyin pul sotuvchiga o'tadi", "Account savdo", 1, 30),
    "vip_price_per_day": Spec("money", 5_000, "VIP e'lon narxi (so'm / kun)", "Account savdo", 0, 10_000_000),
    # Ijara
    "rent_discount_24": Spec("percent", 10, "Chegirma: 24 soat (%)", "Account ijara", 0, 90),
    "rent_discount_72": Spec("percent", 20, "Chegirma: 3 kun (%)", "Account ijara", 0, 90),
    "rent_discount_168": Spec("percent", 30, "Chegirma: 1 hafta (%)", "Account ijara", 0, 90),
    "rent_deposit_type": Spec("choice", "fixed", "Ijara depoziti turi", "Account ijara",
                              choices={"percent": "Ijara narxidan foiz", "fixed": "Aniq summa"}),
    "rent_deposit_percent": Spec("percent", 100, "Depozit: ijara narxining necha foizi (%)", "Account ijara", 0, 1000,
                                 show_if=("rent_deposit_type", "percent")),
    "rent_deposit_fixed": Spec("money", 50_000, "Depozit: aniq summa (so'm)", "Account ijara", 0, 100_000_000,
                               show_if=("rent_deposit_type", "fixed")),
    "rent_commission_percent": Spec("percent", 10, "Ijaradan platforma ulushi (%)", "Account ijara", 0, 90),
    # Boost
    "boost_express_percent": Spec("percent", 30, "Express boost ustamasi (%)", "Boost", 0, 500),
    "boost_hero_percent": Spec("percent", 15, "Qahramon tanlash ustamasi (%)", "Boost", 0, 500),
    "boost_lane_percent": Spec("percent", 10, "Liniya tanlash ustamasi (%)", "Boost", 0, 500),
    "boost_star_epic": Spec("money", 6_000, "1 yulduz narxi: Epic (so'm)", "Boost", 100),
    "boost_star_legend": Spec("money", 8_000, "1 yulduz narxi: Legend (so'm)", "Boost", 100),
    "boost_star_mythic": Spec("money", 10_000, "1 yulduz narxi: Mythic 0–24★ (so'm)", "Boost", 100),
    "boost_star_honor": Spec("money", 12_000, "1 yulduz narxi: Mythic 25–49★ (so'm)", "Boost", 100),
    "boost_star_glory": Spec("money", 15_000, "1 yulduz narxi: Mythical Glory 50★+ (so'm)", "Boost", 100),
    "boost_stars_per_day": Spec("money", 20, "Kuniga yulduz (oddiy)", "Boost", 1, 500),
    "boost_express_stars_per_day": Spec("money", 40, "Kuniga yulduz (Express)", "Boost", 1, 500),
    "booster_share_percent": Spec("percent", 70, "Booster ulushi (%)", "Boost", 0, 100),
}

# ---------------------------------------------------------------- Arena (ball pulga almashtirilmaydi)
SCHEMA.update({
    "pts_tournament_join": Spec("money", 20, "Ball: turnirda ishtirok", "Arena: ball", 0, 100_000),
    "pts_tournament_win": Spec("money", 100, "Ball: turnirda g'alaba", "Arena: ball", 0, 100_000),
    "pts_prediction": Spec("money", 50, "Ball: to'g'ri prognoz", "Arena: ball", 0, 100_000),
    "tg_auto": Spec("choice", "on", "Telegram Premium va Stars avtomatik (API orqali)", "Telegram: Premium va Stars",
                    choices={"on": "Avtomatik", "off": "Qo'lda"}),
    "mlbb_live_stats": Spec("choice", "on", "Tirik MLBB statistikasi (Rone Arena API: g'alaba %, tier, counter)", "Arena: ball",
                            choices={"on": "Yoqilgan", "off": "O'chirilgan"}),
    "pts_quiz": Spec("money", 10, "Ball: viktorinada to'g'ri javob", "Arena: ball", 0, 100_000),
    "pts_vote": Spec("money", 5, "Ball: haftaning qahramoniga ovoz", "Arena: ball", 0, 100_000),
    "season_days": Spec("money", 30, "Sezon davomiyligi (kun)", "Arena: ball", 1, 365),
    "ex_boost_discount_cost": Spec("money", 500, "Almashtirish: Boost chegirmasi (ball)", "Arena: almashtirish", 1, 1_000_000),
    "ex_boost_discount_percent": Spec("percent", 5, "Boost chegirmasi (%)", "Arena: almashtirish", 1, 90),
    "ex_vip_3d_cost": Spec("money", 1_000, "Almashtirish: VIP e'lon 3 kun (ball)", "Arena: almashtirish", 1, 1_000_000),
    "ex_free_tournament_cost": Spec("money", 1_500, "Almashtirish: turnirga bepul kirish (ball)", "Arena: almashtirish", 1, 1_000_000),
})
MISSIONS = {  # kalit: (davr, nom, maqsad, standart mukofot)
    "login": ("daily", "Ilovaga kirish", 1, 10),
    "join_tournament": ("daily", "1 ta turnirga yozilish", 1, 20),
    "invite": ("daily", "Do'stni taklif qilish", 1, 50),
    "play_3": ("weekly", "3 ta turnirda qatnashish", 3, 100),
    "partner_video": ("weekly", "Hamkor videosi yuborish", 1, 50),
    "any_service": ("weekly", "Istalgan xizmatdan foydalanish", 1, 30),
    "quiz": ("daily", "«Qahramonni top» viktorinasini yechish", 5, 30),
    "hero_vote": ("weekly", "Haftaning qahramoniga ovoz berish", 1, 20),
}
for _k, (_p, _n, _g, _r) in MISSIONS.items():
    SCHEMA[f"mission_{_k}"] = Spec("money", _r, f"Vazifa mukofoti: {_n} (ball)", "Arena: vazifalar", 0, 100_000)

# ---------------------------------------------------------------- Hamkor dasturi
SCHEMA.update({
    # Akkaunt savdo: xavfsizlik
    "hold_days_new": Spec("money", 7, "Yangi sotuvchi: tasdiqdan keyin pul necha kun ushlanadi (akkaunt qaytarib olinmasligi uchun)", "Account savdo", 0, 30),
    "hold_days_verified": Spec("money", 2, "Tasdiqlangan sotuvchi: pul necha kun ushlanadi", "Account savdo", 0, 30),
    "deliver_hours": Spec("money", 12, "Sotuvchi akkaunt ma'lumotini necha soatda berishi kerak (aks holda pul qaytadi)", "Account savdo", 1, 72),
    "market_account_id": Spec("choice", "on", "E'lon uchun akkaunt ID majburiy (bir akkaunt ikki marta sotilmasin)", "Account savdo", choices={"on": "Majburiy", "off": "Ixtiyoriy"}),
    "market_min_photos": Spec("money", 3, "E'longa kamida nechta rasm kerak", "Account savdo", 0, 6),
    "strikes_block": Spec("money", 3, "Necha marta muddatni buzgan sotuvchi e'lon qo'sha olmaydi", "Account savdo", 1, 20),
    "chat_block_contacts": Spec("choice", "on", "Chatda telefon, havola va karta yozishni to'sish (garantdan tashqari savdoga qarshi)", "Account savdo", choices={"on": "To'sish", "off": "Ruxsat"}),
    # VAYNEXO Plus
    "plus_on": Spec("choice", "on", "VAYNEXO Plus obunasi", "VAYNEXO Plus", choices={"on": "Yoqilgan", "off": "O'chiq"}),
    "plus_price": Spec("money", 39_000, "Oylik narx (so'm)", "VAYNEXO Plus", 1_000, 10_000_000),
    "plus_cashback": Spec("percent", 3, "Har xariddan keshbek (%)", "VAYNEXO Plus", 0, 20),
    # Skin jamg'armasi
    "savings_on": Spec("choice", "on", "Skin jamg'armasi", "Skin jamg'armasi", choices={"on": "Yoqilgan", "off": "O'chiq"}),
    "savings_bonus": Spec("percent", 3, "Maqsadga yetib xarid qilganda bonus (%)", "Skin jamg'armasi", 0, 20),
    "savings_min_days": Spec("money", 14, "Bonus uchun: yarmi kamida necha kun turishi kerak", "Skin jamg'armasi", 0, 180),
    # Striminerlar
    "stream_on": Spec("choice", "on", "Efirda donat (striminerlar)", "Striminerlar", choices={"on": "Yoqilgan", "off": "O'chiq"}),
    "stream_fee": Spec("percent", 10, "Pul donatidan platforma ulushi (%)", "Striminerlar", 0, 50),
    "stream_min": Spec("money", 5_000, "Eng kam pul donati (so'm)", "Striminerlar", 1_000, 10_000_000),
    # Pro bilan o'yna
    "pro_on": Spec("choice", "on", "Pro bilan o'yna (auksion)", "Pro bilan o'yna", choices={"on": "Yoqilgan", "off": "O'chiq"}),
    "pro_fee": Spec("percent", 15, "Auksiondan platforma ulushi (%)", "Pro bilan o'yna", 0, 50),
    "pro_min_bid": Spec("money", 20_000, "Eng kam boshlang'ich narx (so'm)", "Pro bilan o'yna", 1_000, 100_000_000),
    # Birgalikda to'laymiz / Orzu ro'yxati
    "split_on": Spec("choice", "on", "Birgalikda to'laymiz va Orzu ro'yxati", "Birgalikda to'lov", choices={"on": "Yoqilgan", "off": "O'chiq"}),
    "split_hours": Spec("money", 24, "Yig'ish muddati (soat). Tugasa pul hammaga qaytadi", "Birgalikda to'lov", 1, 168),
    "split_min": Spec("money", 1_000, "Eng kam ulush (so'm)", "Birgalikda to'lov", 1_000, 1_000_000),
    # Draft Jang
    "duel_on": Spec("choice", "on", "Draft Jang", "Draft Jang", choices={"on": "Yoqilgan", "off": "O'chiq"}),
    "duel_win_points": Spec("money", 20, "G'olibga Arena ball", "Draft Jang", 0, 1000),
    "duel_lose_points": Spec("money", 5, "Qatnashgan uchun Arena ball", "Draft Jang", 0, 1000),
    # Kunlik check-in va Meta bashorat
    "checkin_points": Spec("money", 5, "Kunlik check-in: har kun ball", "Kunlik seriya", 0, 1000),
    "meta_points": Spec("money", 50, "Meta bashorat: to'g'ri topganga ball", "Kunlik seriya", 0, 1000),
    # VAY ball
    "vay_on": Spec("choice", "on", "VAY ball tizimi", "VAY ball", choices={"on": "Yoqilgan", "off": "O'chiq"}),
    "vay_per": Spec("money", 1_000, "Har necha so'm xaridga 1 VAY", "VAY ball", 100, 1_000_000),
    "vay_th_2": Spec("money", 500, "2-daraja (Jangchi): VAY", "VAY ball", 1, 10_000_000),
    "vay_th_3": Spec("money", 3_000, "3-daraja (Usta): VAY", "VAY ball", 1, 10_000_000),
    "vay_th_4": Spec("money", 10_000, "4-daraja (Legenda): VAY", "VAY ball", 1, 10_000_000),
    "vay_cb_1": Spec("percent", 0, "Rekrut: keshbek (%)", "VAY ball", 0, 20),
    "vay_cb_2": Spec("percent", 1, "Jangchi: keshbek (%)", "VAY ball", 0, 20),
    "vay_cb_3": Spec("percent", 1, "Usta: keshbek (%)", "VAY ball", 0, 20),
    "vay_cb_4": Spec("percent", 2, "Legenda: keshbek (%)", "VAY ball", 0, 20),
    # Do'konlar
    "shop_on": Spec("choice", "on", "«O'z do'koningni och» bo'limi", "Do'konlar", choices={"on": "Yoqilgan", "off": "O'chiq"}),
    "shop_pct_1": Spec("percent", 3, "Bronza: komissiya (%)", "Do'konlar", 0, 30),
    "shop_pct_2": Spec("percent", 4, "Kumush: komissiya (%)", "Do'konlar", 0, 30),
    "shop_pct_3": Spec("percent", 5, "Oltin: komissiya (%)", "Do'konlar", 0, 30),
    "shop_pct_4": Spec("percent", 6, "Brilliant: komissiya (%)", "Do'konlar", 0, 30),
    "shop_th_2": Spec("money", 5_000_000, "Kumush: savdo summasi (so'm)", "Do'konlar", 1, 10_000_000_000),
    "shop_th_3": Spec("money", 20_000_000, "Oltin: savdo summasi (so'm)", "Do'konlar", 1, 10_000_000_000),
    "shop_th_4": Spec("money", 50_000_000, "Brilliant: savdo summasi (so'm)", "Do'konlar", 1, 10_000_000_000),
    "partner_min_views": Spec("money", 3_000, "Eng kam ko'rish", "Hamkor dasturi", 0, 100_000_000),
    "partner_count_days": Spec("money", 10, "Ko'rishlar necha kundan keyin hisoblanadi", "Hamkor dasturi", 1, 60),
    "partner_interval_days": Spec("money", 2, "Necha kunda 1 ta video", "Hamkor dasturi", 0, 60),
    "partner_min_like_ratio": Spec("percent", 3, "Layk / ko'rish nisbati, kamida (%)", "Hamkor dasturi", 0, 100),
    "partner_tier2_views": Spec("money", 10_000, "2-daraja: ko'rish", "Hamkor dasturi", 1, 100_000_000),
    "partner_tier3_views": Spec("money", 25_000, "3-daraja: ko'rish", "Hamkor dasturi", 1, 100_000_000),
    "partner_tier4_views": Spec("money", 50_000, "4-daraja: ko'rish", "Hamkor dasturi", 1, 100_000_000),
    "partner_code_bonus": Spec("money", 3_000, "Hamkor promo-kodi: foydalanuvchiga bonus (so'm)", "Hamkor dasturi", 0, 1_000_000),
    "partner_code_points": Spec("money", 50, "Hamkor promo-kodi: hamkorga ball (har foydalanish)", "Hamkor dasturi", 0, 100_000),
    "partner_code_min_videos": Spec("money", 1, "Promo-kod olish uchun tasdiqlangan video soni", "Hamkor dasturi", 0, 100),
})

# Stars paketlari bonusi (paket -> qo'shimcha yulduz)
STARS_BONUS_DEFAULT = {250: 5, 500: 15, 1_000: 40, 2_500: 120}
for _n, _b in STARS_BONUS_DEFAULT.items():
    SCHEMA[f"stars_bonus_{_n}"] = Spec("money", _b, f"Stars bonusi: {_n} paket (+ yulduz)", "Telegram: Premium va Stars", 0, 100_000)

# ---------------------------------------------------------------- Telegram (Fragment orqali)
_FIX, _PCT = ("tg_price_mode", "fixed"), ("tg_price_mode", "percent")
SCHEMA.update({
    "tg_price_mode": Spec("choice", "fixed", "Premium va Stars narxi qanday belgilanadi", "Telegram: Premium va Stars",
                          choices={"fixed": "Aniq narx", "percent": "Fragment tannarxi + foiz"}),
    "tg_markup_percent": Spec("percent", 15, "Ustama: Fragment tannarxiga necha foiz qo'shiladi (%)", "Telegram: Premium va Stars", 0, 500, show_if=_PCT),
    "stars_cost": Spec("money", 190, "Fragment tannarxi: 1 Star (so'm)", "Telegram: Premium va Stars", 1, 100_000, show_if=_PCT),
    "stars_price": Spec("money", 220, "Sotuv narxi: 1 Star (so'm)", "Telegram: Premium va Stars", 1, 100_000, show_if=_FIX),
})
for _m, _cost, _price in ((1, 60_000, 69_000), (3, 165_000, 189_000), (6, 300_000, 349_000), (12, 520_000, 599_000)):
    SCHEMA[f"premium_cost_{_m}"] = Spec("money", _cost, f"Fragment tannarxi: Premium {_m} oy (so'm)", "Telegram: Premium va Stars", 1, show_if=_PCT)
    SCHEMA[f"premium_price_{_m}"] = Spec("money", _price, f"Sotuv narxi: Premium {_m} oy (so'm)", "Telegram: Premium va Stars", 1, show_if=_FIX)
for _code, _name, _price in (("heart", "Yurak", 15_000), ("bear", "Ayiqcha", 15_000), ("box", "Sovg'a qutisi", 25_000),
                             ("rose", "Gul", 25_000), ("cup", "Kubok", 50_000), ("diamond", "Brilliant", 100_000)):
    SCHEMA[f"gift_price_{_code}"] = Spec("money", _price, f"Gift: {_name} (so'm)", "Telegram: Gift va NFT", 1)
for _code, _name, _price in (("gift", "NFT sovg'a", 350_000), ("username", "Username", 120_000), ("number", "Anonim raqam", 90_000)):
    SCHEMA[f"nft_price_{_code}"] = Spec("money", _price, f"NFT: {_name} (so'm)", "Telegram: Gift va NFT", 1)


# ---------------------------------------------------------------- Donat narxi (API tannarxi USD → so'm)
SCHEMA.update({
    "donate_usd_rate": Spec("money", 12_800, "Dollar kursi (1 USD necha so'm) — API narxlarini so'mga o'giradi", "Donat narxi", 1_000, 100_000),
    "donate_markup_percent": Spec("percent", 10, "Ustama: tannarxga necha foiz qo'shiladi (%)", "Donat narxi", 0, 300),
})

# ---------------------------------------------------------------- Bo'limlarni yoqish/o'chirish (standart: faqat donat)
FEATURES = {  # kalit: nomi
    "market": "Account savdo", "rent": "Account ijara", "boost": "Boost xizmati", "tg": "Telegram xizmatlar (Premium/Stars)",
    "arena": "Arena (turnir, reyting)", "partner": "Hamkor dasturi", "ai": "AI yordamchi", "top": "Top xaridorlar",
}
DEFAULT_OFF = {"ai", "market", "rent", "boost"}  # «Tez kunda»: admin panel → Ko'proq → Bo'limlar orqali ochiladi
for _k, _n in FEATURES.items():
    SCHEMA[f"feature_{_k}"] = Spec("choice", "off" if _k in DEFAULT_OFF else "on", f"{_n}", "Bo'limlar (ilovada ko'rinishi)", choices={"on": "Yoqilgan", "off": "O'chirilgan"})


async def features(session: AsyncSession) -> dict[str, bool]:
    return {k: (await get_value(session, f"feature_{k}")) == "on" for k in FEATURES}


def _default(key: str):
    spec = SCHEMA[key]
    return spec.default if spec.default is not None else getattr(settings, key)


def _parse(spec: Spec, raw):
    if spec.kind == "choice":
        value = str(raw)
        if value not in spec.choices:
            raise ValueError(value)
        return value
    return int(raw)


async def get_value(session: AsyncSession, key: str):
    raw = await session.scalar(select(AppSetting.value).where(AppSetting.key == key))
    if raw is None:
        return _default(key)
    try:
        return _parse(SCHEMA[key], raw)
    except (TypeError, ValueError):
        return _default(key)


async def get_many(session: AsyncSession, *keys: str) -> dict:
    return {k: await get_value(session, k) for k in keys}


async def get_all(session: AsyncSession) -> list[dict]:
    return [
        {"key": k, "value": await get_value(session, k), "kind": s.kind, "min": s.lo, "max": s.hi, "label": s.label,
         "group": s.group, "choices": [{"v": v, "label": lbl} for v, lbl in s.choices.items()],
         "show_if": {"key": s.show_if[0], "value": s.show_if[1]} if s.show_if else None}
        for k, s in SCHEMA.items()
    ]


async def set_value(session: AsyncSession, key: str, value) -> None:
    spec = SCHEMA.get(key)
    if spec is None:
        raise AppError("bad_setting", "Noma'lum sozlama")
    try:
        value = _parse(spec, value)
    except (TypeError, ValueError) as e:
        raise AppError("bad_setting", "Qiymat noto'g'ri") from e
    if spec.kind != "choice" and not spec.lo <= value <= spec.hi:
        raise AppError("bad_setting", f"Qiymat {spec.lo} dan {spec.hi} gacha bo'lishi kerak")
    row = await session.get(AppSetting, key)
    if row is None:
        session.add(AppSetting(key=key, value=str(value)))
    else:
        row.value = str(value)
