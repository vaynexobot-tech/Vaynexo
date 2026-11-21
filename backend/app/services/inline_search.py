"""Inline qidiruv: istalgan chatda «@bot 86» yoki «@bot pubg 660» — paket va narxlar ro'yxati.

Faqat faol o'yinlar va faol paketlar. Natija — Telegram InlineQueryResultArticle uchun oddiy lug'atlar (test qilish oson).
"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DonateGame, DonatePackage

# Qisqa nomlar → o'yin kodi (slug)
ALIASES = {
    "ml": "ML", "mlbb": "ML", "mobile": "ML", "legends": "ML", "mobilelegends": "ML",
    "mc": "MC", "chess": "MC", "magic": "MC",
    "pubg": "pubg-mobile", "pubgm": "pubg-mobile", "uc": "pubg-mobile",
    "ff": "free-fire", "free": "free-fire", "fire": "free-fire", "freefire": "free-fire",
    "genshin": "genshin-impact", "roblox": "roblox", "robux": "roblox", "steam": "steam",
    "hok": "honor-of-kings", "honor": "honor-of-kings", "delta": "delta-force", "standoff": "standoff-2", "so2": "standoff-2",
    "blood": "blood-strike", "breakout": "arena-breakout",
}
STOP = {"almaz", "almazlar", "olmos", "olmoslar", "diamond", "diamonds", "donat", "donate", "paket", "paketlar", "sotib", "olish",
        "narx", "narxi", "uchun", "va", "dona", "ta"}
MAX_RESULTS = 30


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def parse_query(q: str) -> tuple[list[str], list[int]]:
    """«ML 86 almaz» → (["ml"], [86]); «1 412» kabi bo'shliqli sonlar ham bitta son bo'ladi."""
    q = re.sub(r"(?<=\d)[\s.,](?=\d{3}\b)", "", (q or "").lower())
    words, nums = [], []
    for t in re.findall(r"[a-zа-яё0-9']+", q):
        if t.isdigit():
            nums.append(int(t))
        elif t not in STOP and len(t) >= 2:
            words.append(t)
    return words, nums


def _game_matches(g: DonateGame, word: str) -> bool:
    if ALIASES.get(word) == g.slug:
        return True
    w = _norm(word)
    return len(w) >= 3 and (w in _norm(g.name) or w in _norm(g.slug))


async def search(session: AsyncSession, query: str) -> list[dict]:
    words, nums = parse_query(query)
    games = list(await session.scalars(select(DonateGame).where(DonateGame.is_active.is_(True)).order_by(DonateGame.sort, DonateGame.name)))
    if words:
        games = [g for g in games if any(_game_matches(g, w) for w in words)]
        if not games:
            return []
    by_slug = {g.slug: g for g in games}
    if not by_slug:
        return []
    pkgs = list(await session.scalars(select(DonatePackage).where(
        DonatePackage.game.in_(list(by_slug)), DonatePackage.is_active.is_(True)).order_by(DonatePackage.sort, DonatePackage.price)))
    pkgs = [p for p in pkgs if not by_slug[p.game].provider_id or p.provider_id in (None, by_slug[p.game].provider_id)]  # faqat tanlangan API
    if nums:
        def hit(p: DonatePackage) -> bool:
            total = (p.diamonds or 0) + (p.bonus or 0)
            return any(n in (p.diamonds, total) or re.search(rf"(?<!\d){n}(?!\d)", p.name.replace(" ", "")) for n in nums)

        pkgs = [p for p in pkgs if hit(p)]
    else:  # son yo'q: har o'yindan bir nechta (bitta o'yin bo'lsa — ko'proq)
        per = 20 if len(by_slug) == 1 else 4
        seen: dict[str, int] = {}
        out = []
        for p in pkgs:
            if seen.get(p.game, 0) < per:
                seen[p.game] = seen.get(p.game, 0) + 1
                out.append(p)
        pkgs = out
    order = {g.slug: i for i, g in enumerate(games)}
    pkgs.sort(key=lambda p: (order.get(p.game, 999), p.sort, p.price))
    return [{"id": p.id, "game": p.game, "game_name": by_slug[p.game].name, "name": p.name, "price": p.price,
             "voucher": p.delivery == "voucher",
             "logo": by_slug[p.game].logo_url if (by_slug[p.game].logo_url or "").startswith("https://") else None}
            for p in pkgs[:MAX_RESULTS]]
