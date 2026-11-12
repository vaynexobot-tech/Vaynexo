"""Fon ishlari (arq):  python -m app.worker

* send_tg            — Telegram xabarlari (flood-limitni hisobga olib)
* fulfil_donate      — almazni provayder orqali yetkazish
* post_boost / update_boost_post — boosterlar guruhidagi e'lon
* cron: muddati o'tgan to'ldirishlar, garantni avto-yakunlash, osilib qolgan donatlar
"""

import logging
from datetime import datetime, timedelta, timezone

from aiogram.exceptions import TelegramForbiddenError, TelegramNetworkError, TelegramRetryAfter
from arq import Retry, cron
from sqlalchemy import select

from app.bot.handlers import boost_post_kb, boost_post_text, get_share_pct
from app.bot.instance import get_bot
from app.config import settings
from app.db import SessionLocal
from app.models import BoostOrder, DonateOrder
from app.queue import LITE, redis_settings
from app.services import donate, market, p2p, rental
from app.services import services as svc
from app.services.notify import Outbox

log = logging.getLogger(__name__)


async def send_tg(ctx, chat_id: int, text: str, markup: dict | None = None):
    thread = None
    if markup and "_thread" in markup:
        markup = dict(markup)
        thread = markup.pop("_thread")
        markup = markup or None
    try:
        await get_bot().send_message(chat_id, text, reply_markup=markup, message_thread_id=thread)
    except TelegramRetryAfter as e:
        raise Retry(defer=e.retry_after + 1) from e
    except TelegramForbiddenError:
        log.info("Foydalanuvchi botni bloklagan: %s", chat_id)
    except TelegramNetworkError as e:  # vaqtinchalik tarmoq xatosi — keyinroq qayta urinamiz
        raise Retry(defer=15 * ctx.get("job_try", 1)) from e
    except Exception:
        log.exception("Xabar yuborilmadi chat_id=%s", chat_id)


async def fulfil_donate(ctx, order_id: int, mode: str = "create"):
    out = Outbox()
    nxt = await donate.fulfil_step(SessionLocal, order_id, mode, out)
    await out.flush()
    if nxt:
        next_mode, delay = nxt
        await ctx["redis"].enqueue_job("fulfil_donate", order_id, next_mode, _defer_by=timedelta(seconds=delay))


async def post_boost(ctx, order_id: int):
    from app.services.notify import get_booster_group

    group = await get_booster_group()
    if not group:
        out = Outbox()
        out.admins(f"🚀 Yangi boost buyurtma #{order_id} (boosterlar guruhi ulanmagan — guruhda /booster_guruh yozing).", topic="boost")
        await out.flush()
        return
    await get_share_pct()
    async with SessionLocal() as session, session.begin():
        o = await session.scalar(select(BoostOrder).where(BoostOrder.id == order_id).with_for_update())
        if o is None or o.group_message_id:
            return
        msg = await get_bot().send_message(group, boost_post_text(o), reply_markup=boost_post_kb(o))
        o.group_message_id = msg.message_id


async def update_boost_post(ctx, order_id: int):
    await get_share_pct()
    async with SessionLocal() as session:
        o = await session.get(BoostOrder, order_id)
    from app.services.notify import get_booster_group

    group = await get_booster_group()
    if o is None or not o.group_message_id or not group:
        return
    try:
        await get_bot().edit_message_text(
            boost_post_text(o), chat_id=group, message_id=o.group_message_id, reply_markup=boost_post_kb(o)
        )
    except Exception:
        log.debug("Guruh xabarini yangilab bo'lmadi", exc_info=True)


# ------------------------------------------------------------------ cron
async def cron_expire_topups(ctx):
    async with SessionLocal() as session, session.begin():
        await p2p.expire_topups(session)
    out = Outbox()
    async with SessionLocal() as session, session.begin():
        await p2p.remind_unmatched(session, out)
    await out.flush()


async def cron_auto_release(ctx):
    out = Outbox()
    async with SessionLocal() as session, session.begin():
        await market.auto_release(session, out)
    async with SessionLocal() as session, session.begin():
        await svc.boost_auto_confirm(session, out)
    async with SessionLocal() as session, session.begin():
        await rental.tick(session, out)
    async with SessionLocal() as session, session.begin():
        await svc.tournament_reminders(session, out)
    await out.flush()


async def cron_rescue_donates(ctx):
    """Navbatga tushmay qolgan (masalan, Redis vaqtincha ishlamagan) donatlarni qayta yuboradi."""
    limit_time = datetime.now(timezone.utc) - timedelta(minutes=3)
    async with SessionLocal() as session:
        ids = list(await session.scalars(
            select(DonateOrder.id).where(DonateOrder.status == "processing", DonateOrder.attempts == 0,
                                         DonateOrder.created_at < limit_time).limit(50)
        ))
    for oid in ids:
        await ctx["redis"].enqueue_job("fulfil_donate", oid, "create", _job_id=f"rescue:{oid}")


async def startup(ctx):
    logging.basicConfig(level=logging.INFO)


async def shutdown(ctx):
    await get_bot().session.close()


class WorkerSettings:
    functions = [send_tg, fulfil_donate, post_boost, update_boost_post]
    cron_jobs = [
        cron(cron_expire_topups, second=0),
        cron(cron_auto_release, minute=set(range(0, 60, 5)), second=10),
        cron(cron_rescue_donates, minute=set(range(1, 60, 2)), second=20),
    ]
    redis_settings = None if LITE else redis_settings()
    on_startup = startup
    on_shutdown = shutdown
    max_jobs = 50
    max_tries = 5


def main() -> None:
    """`python -m app.worker` — arq CLI'siz ishga tushirish (Python 3.12+ da event loop muammosisiz)."""
    import asyncio

    from arq.worker import Worker

    if LITE:
        raise SystemExit("REDIS_URL bo'sh — yengil rejimda fon ishlari API ichida bajariladi, worker kerak emas.")
    asyncio.set_event_loop(asyncio.new_event_loop())
    worker = Worker(
        functions=WorkerSettings.functions, cron_jobs=WorkerSettings.cron_jobs, redis_settings=WorkerSettings.redis_settings,
        on_startup=startup, on_shutdown=shutdown, max_jobs=WorkerSettings.max_jobs, max_tries=WorkerSettings.max_tries,
    )
    worker.run()


if __name__ == "__main__":
    main()
