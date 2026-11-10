"""Telegram xizmatlari (narxlar admin paneldan) va boost narxlari (so'm)."""

PREMIUM_MONTHS = (1, 3, 6, 12)
STARS_PRESETS = [50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000]
STARS_MIN, STARS_MAX = 50, 100_000
GIFTS = {"heart": "Yurak", "bear": "Ayiqcha", "box": "Sovg'a qutisi", "rose": "Gul", "cup": "Kubok", "diamond": "Brilliant"}
NFT = {"gift": "NFT sovg'a", "username": "Username", "number": "Anonim raqam"}


async def tg_prices(session) -> dict:
    """Premium va Stars: aniq narx yoki Fragment tannarxi + ustama (admin paneldan). Gift va NFT: aniq narx."""
    from app.services import app_settings as A

    mode = await A.get_value(session, "tg_price_mode")
    if mode == "percent":
        k = 100 + await A.get_value(session, "tg_markup_percent")
        premium = {m: -(-await A.get_value(session, f"premium_cost_{m}") * k // 100) for m in PREMIUM_MONTHS}  # yuqoriga yaxlitlash
        star_x100 = await A.get_value(session, "stars_cost") * k  # 1 Star narxi × 100 (kasr qismini yo'qotmaslik uchun)
    else:
        premium = {m: await A.get_value(session, f"premium_price_{m}") for m in PREMIUM_MONTHS}
        star_x100 = await A.get_value(session, "stars_price") * 100
    gifts = {c: (n, await A.get_value(session, f"gift_price_{c}")) for c, n in GIFTS.items()}
    nft = {c: (n, await A.get_value(session, f"nft_price_{c}")) for c, n in NFT.items()}
    return {"mode": mode, "premium": premium, "star_x100": star_x100, "gifts": gifts, "nft": nft}


def stars_total(amount: int, star_x100: int) -> int:
    return -(-amount * star_x100 // 100)  # yuqoriga yaxlitlab, butun so'm


async def public_catalog(session) -> dict:
    p = await tg_prices(session)
    return {
        "premium": [{"months": m, "price": price} for m, price in p["premium"].items()],
        "stars": {"presets": STARS_PRESETS, "rate": p["star_x100"] / 100, "min": STARS_MIN, "max": STARS_MAX,
                  "preset_prices": {n: stars_total(n, p["star_x100"]) for n in STARS_PRESETS}},
        "gifts": [{"code": c, "name": n, "price": price} for c, (n, price) in p["gifts"].items()],
        "nft": [{"code": c, "name": n, "price": price} for c, (n, price) in p["nft"].items()],
    }


# ---------------------------------------------------------------- Boost
# Har divizionda 5 yulduz. Epic V..I = 0..24, Legend V..I = 25..49, Mythic = 50+.
DIVISIONS = ["V", "IV", "III", "II", "I"]
STAR_PRICE = [  # (shu pozitsiyadan boshlab, 1 yulduz narxi)
    (0, 4_000),     # Epic
    (25, 5_000),    # Legend
    (50, 7_000),    # Mythic 0-24
    (75, 8_000),    # Mythic Honor 25-49
    (100, 10_000),  # Mythic Glory 50+
]
TARGETS = ("Legend", "Mythic", "M. Glory")
LANES = ("", "Gold", "Mid", "EXP", "Jungle", "Roam")
LOGIN_METHODS = ("moonton", "google", "telegram", "whatsapp")
MAX_MYTHIC_STARS = 300


def position(rank: str, division: str = "V", stars: int = 0) -> int:
    if rank == "Epic":
        return DIVISIONS.index(division) * 5
    if rank == "Legend":
        return 25 + DIVISIONS.index(division) * 5
    if rank == "Mythic":
        return 50 + max(0, stars)
    raise ValueError(rank)


def target_position(target: str, stars: int) -> int:
    if target == "Legend":
        return position("Legend", "I")
    if target == "Mythic":
        return 50 + max(1, stars)
    if target == "M. Glory":
        return 50 + max(50, stars)
    raise ValueError(target)


def star_price(pos: int) -> int:
    price = STAR_PRICE[0][1]
    for start, p in STAR_PRICE:
        if pos >= start:
            price = p
    return price


def boost_price(cur_rank: str, cur_div: str, cur_stars: int, target: str, target_stars: int) -> tuple[int, int, int]:
    """(narx, boshlang'ich pozitsiya, maqsad pozitsiya)."""
    start = position(cur_rank, cur_div, cur_stars)
    end = target_position(target, target_stars)
    if end <= start:
        raise ValueError("Maqsad rank hozirgisidan yuqori bo'lishi kerak")
    if end - 50 > MAX_MYTHIC_STARS:
        raise ValueError("Juda ko'p yulduz")
    return sum(star_price(p) for p in range(start, end)), start, end
