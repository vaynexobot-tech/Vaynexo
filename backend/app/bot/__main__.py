"""Botni polling rejimida ishga tushirish (BOT_WEBHOOK_URL bo'sh bo'lganda):

    python -m app.bot
"""

import asyncio
import logging

from aiogram import Dispatcher

from app.bot.handlers import router
from app.bot.instance import get_bot
from app.config import settings


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = get_bot()
    dp = Dispatcher()
    dp.include_router(router)
    if settings.bot_webhook_url:
        logging.warning("BOT_WEBHOOK_URL o'rnatilgan — bot API ichida webhook orqali ishlaydi, polling kerak emas.")
        return
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
