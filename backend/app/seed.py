"""Boshlang'ich donat paketlari (bir marta):  python -m app.seed

Narx va provider_sku larni admin paneldan o'zgartirish mumkin.
SKU — provayderingiz mahsulot kodi; haqiqiy kodlarni qo'yish shart.
"""

import asyncio

from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import DonatePackage

ML = [
    ("11 almaz", 11, 0, 2_500), ("22 almaz", 22, 0, 4_900), ("56 almaz", 56, 0, 12_000), ("86 almaz", 78, 8, 18_500),
    ("172 almaz", 156, 16, 37_000), ("257 almaz", 234, 23, 55_000), ("344 almaz", 312, 32, 73_000),
    ("514 almaz", 468, 46, 109_000), ("706 almaz", 625, 81, 145_000), ("1412 almaz", 1250, 162, 289_000),
    ("2195 almaz", 1860, 335, 445_000), ("3688 almaz", 3099, 589, 739_000), ("Haftalik propusk", 0, 0, 22_000),
]
MC = [("56 almaz", 56, 0, 12_500), ("172 almaz", 156, 16, 38_000), ("344 almaz", 312, 32, 74_000), ("706 almaz", 625, 81, 147_000)]


async def main() -> None:
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
