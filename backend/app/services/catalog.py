"""Telegram xizmatlari va boost narxlari (so'm). Narxlarni shu yerda o'zgartiring."""

from app.config import settings

PREMIUM = {1: 69_000, 3: 189_000, 6: 349_000, 12: 599_000}
STARS_PRESETS = [50, 100, 250, 500, 1_000, 2_500, 5_000, 10_000]
STARS_MIN, STARS_MAX = 50, 100_000
GIFTS = {
    "heart": ("Yurak", 15_000),
    "bear": ("Ayiqcha", 15_000),
    "box": ("Sovg'a qutisi", 25_000),
    "rose": ("Gul", 25_000),
    "cup": ("Kubok", 50_000),
    "diamond": ("Brilliant", 100_000),
}
NFT = {
    "gift": ("NFT sovg'a", 350_000),
    "username": ("Username", 120_000),
    "number": ("Anonim raqam", 90_000),
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


def public_catalog() -> dict:
    return {
        "premium": [{"months": m, "price": p} for m, p in PREMIUM.items()],
        "stars": {"presets": STARS_PRESETS, "rate": settings.stars_rate, "min": STARS_MIN, "max": STARS_MAX},
        "gifts": [{"code": c, "name": n, "price": p} for c, (n, p) in GIFTS.items()],
        "nft": [{"code": c, "name": n, "price": p} for c, (n, p) in NFT.items()],
        "boost": {"star_price": STAR_PRICE, "targets": TARGETS, "lanes": LANES[1:]},
    }
