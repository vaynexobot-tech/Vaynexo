"""Boshlang'ich donat paketlari (bir marta):  python -m app.seed

Narx va provider_sku larni admin paneldan o'zgartirish mumkin.
SKU — provayderingiz mahsulot kodi; haqiqiy kodlarni qo'yish shart.
"""

import asyncio

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import DonateGame, DonatePackage

# (slug, nomi, asosiy karta raqami, mashhur) — Yupay do'kon sahifalaridagi nomlar; sinxronlashdan keyin rasm va paketlar keladi.
GAMES = [
    ("ML", "Mobile Legends", 1, False), ("pubg-mobile", "PUBG Mobile", 2, False), ("steam", "Steam", 3, False),
    ("free-fire", "Free Fire", None, True), ("standoff-2", "Standoff 2", None, True), ("delta-force", "Delta Force", None, True),
    ("genshin-impact", "Genshin Impact", None, True), ("roblox", "Roblox", None, True), ("honor-of-kings", "Honor of Kings", None, True),
    ("blood-strike", "Blood Strike", None, True), ("arena-breakout", "Arena Breakout", None, True),
]

ML = [
    ("11 almaz", 11, 0, 2_500), ("22 almaz", 22, 0, 4_900), ("56 almaz", 56, 0, 12_000), ("86 almaz", 78, 8, 18_500),
    ("172 almaz", 156, 16, 37_000), ("257 almaz", 234, 23, 55_000), ("344 almaz", 312, 32, 73_000),
    ("514 almaz", 468, 46, 109_000), ("706 almaz", 625, 81, 145_000), ("1412 almaz", 1250, 162, 289_000),
    ("2195 almaz", 1860, 335, 445_000), ("3688 almaz", 3099, 589, 739_000), ("Haftalik propusk", 0, 0, 22_000),
]
MC = [("56 almaz", 56, 0, 12_500), ("172 almaz", 156, 16, 38_000), ("344 almaz", 312, 32, 74_000), ("706 almaz", 625, 81, 147_000)]


_PID = {"key": "player_id", "label": "Player ID", "placeholder": "123456789", "pattern": r"^\d{5,20}$"}
_ML = [{"key": "player_id", "label": "User ID", "placeholder": "12345678", "pattern": r"^\d{5,20}$"},
       {"key": "server_id", "label": "Zone ID", "placeholder": "1234", "pattern": r"^\d{1,10}$"}]
GAME_FIELDS: dict[str, list[dict]] = {
    "ML": _ML,
    "MC": _ML,
    "pubg-mobile": [{"key": "player_id", "label": "Character ID", "placeholder": "5123456789", "pattern": r"^\d{5,15}$"}],
    "steam": [{"key": "player_id", "label": "Steam login", "placeholder": "login", "pattern": r"^[A-Za-z0-9_.-]{2,64}$"}],
    "free-fire": [_PID],
    "standoff-2": [_PID],
    "delta-force": [_PID],
    "honor-of-kings": [_PID],
    "blood-strike": [_PID],
    "arena-breakout": [_PID],
    "genshin-impact": [{"key": "player_id", "label": "UID", "placeholder": "700000000", "pattern": r"^\d{9,10}$"},
                       {"key": "server_id", "label": "Server", "placeholder": "os_asia", "pattern": r"^[a-z_]{2,20}$"}],
    "roblox": [{"key": "player_id", "label": "Roblox username", "placeholder": "username", "pattern": r"^[A-Za-z0-9_]{3,20}$"}],
}


async def seed_games() -> None:
    """O'yinlar ro'yxati: faqat yo'q bo'lganlari qo'shiladi (admin o'zgartirganlari buzilmaydi). MC yashirin.
    Maydonlari bo'sh qolgan o'yinlarga standart ID maydonlari qo'yiladi."""
    async with SessionLocal() as session, session.begin():
        have = {g.slug: g for g in await session.scalars(select(DonateGame))}
        for i, (slug, name, slot, popular) in enumerate(GAMES):
            if slug not in have:
                session.add(DonateGame(slug=slug, name=name, featured_slot=slot, popular=popular, sort=i,
                                       fields=GAME_FIELDS.get(slug, [_PID]), is_active=True))
        if "MC" not in have:
            session.add(DonateGame(slug="MC", name="Magic Chess", is_active=False, sort=99, fields=_ML))
        for slug, g in have.items():
            if not g.fields:
                g.fields = GAME_FIELDS.get(slug, [_PID])


async def main() -> None:
    await seed_games()
    async with SessionLocal() as session, session.begin():
        if await session.scalar(select(func.count()).select_from(DonatePackage)):
            print("Paketlar allaqachon bor — o'tkazib yuborildi.")
            return
        for game, items in (("ML", ML), ("MC", MC)):
            for i, (name, d, b, price) in enumerate(items):
                session.add(DonatePackage(
                    game=game, name=name, diamonds=d, bonus=b, price=price,
                    provider_sku=f"{game}_{name.split()[0].upper()}", sort=i, is_hot=name.startswith("172"),
                ))
    print("Paketlar qo'shildi.")


if __name__ == "__main__":
    asyncio.run(main())
