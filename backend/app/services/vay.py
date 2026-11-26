"""VAY ball: umr bo'yi yig'iladigan tajriba (XP). Sarflanmaydi, faqat daraja beradi.

- Har bajarilgan xariddan (donat, Telegram xizmat) har `vay_per` so'm uchun 1 VAY.
- Arena'da ishlangan har ball ham 1 VAY (arena.add_points).
- Daraja oshgani sari xariddan hamyonga keshbek (Plus keshbegiga qo'shiladi).
Pulga almashtirilmaydi va tasodifga bog'liq emas.
"""

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.services import app_settings, wallet

LEVELS = [("Rekrut", "🪖"), ("Jangchi", "⚔️"), ("Usta", "🎖"), ("Legenda", "👑")]


async def _cfg(session: AsyncSession) -> dict:
    keys = ["vay_on", "vay_per", "vay_th_2", "vay_th_3", "vay_th_4"] + [f"vay_cb_{i}" for i in range(1, 5)]
    return await app_settings.get_many(session, *keys)


def _level(cfg: dict, xp: int) -> dict:
    ths = [0, int(cfg["vay_th_2"]), int(cfg["vay_th_3"]), int(cfg["vay_th_4"])]
    cbs = [int(cfg[f"vay_cb_{i}"]) for i in range(1, 5)]
    idx = max(i for i, th in enumerate(ths) if xp >= th)
    name, icon = LEVELS[idx]
    nxt = None
    if idx < 3:
        nxt = {"name": LEVELS[idx + 1][0], "icon": LEVELS[idx + 1][1], "need": ths[idx + 1] - xp, "at": ths[idx + 1], "cashback": cbs[idx + 1]}
    return {"level": idx + 1, "name": name, "icon": icon, "cashback": cbs[idx], "from": ths[idx], "next": nxt}


async def on_purchase(session: AsyncSession, user_id: int, kind: str, order_id: int, amount: int) -> dict | None:
    """Bajarilgan xarid: XP beradi va joriy daraja keshbegini hamyonga qaytaradi (idempotent)."""
    cfg = await _cfg(session)
    if cfg["vay_on"] != "on" or amount <= 0:
        return None
    user = await session.scalar(select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True))
    if user is None:
        return None
    from sqlalchemy.dialects.postgresql import insert

    from app.models import PointsEntry

    res = await session.execute(  # bir buyurtma ikki marta hisoblanmasin
        insert(PointsEntry).values(user_id=user_id, amount=0, reason="vay_xp", idem_key=f"vay_xp:{kind}:{order_id}")
        .on_conflict_do_nothing(index_elements=["idem_key"]).returning(PointsEntry.id))
    if res.scalar() is None:
        return None
    lvl = _level(cfg, user.vay_xp)  # keshbek xariddan OLDINGI darajaga qarab
    cb = amount * lvl["cashback"] // 100
    got = 0
    if cb > 0:
        await wallet.credit(session, user_id, cb, "vay_cashback", f"vay_cb:{kind}:{order_id}", ref_type="vay", ref_id=user_id)
        got = cb
    xp = amount // int(cfg["vay_per"])
    if xp > 0:
        await session.execute(update(User).where(User.id == user_id).values(vay_xp=User.vay_xp + xp))
    return {"xp": xp, "cashback": got}


async def overview(session: AsyncSession, user: User) -> dict:
    cfg = await _cfg(session)
    return {"enabled": cfg["vay_on"] == "on", "xp": user.vay_xp or 0, "per": int(cfg["vay_per"]), **_level(cfg, user.vay_xp or 0),
            "levels": [{"name": LEVELS[i][0], "icon": LEVELS[i][1], "from": [0, int(cfg["vay_th_2"]), int(cfg["vay_th_3"]), int(cfg["vay_th_4"])][i],
                        "cashback": int(cfg[f"vay_cb_{i + 1}"])} for i in range(4)]}
