from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from app.config import settings

_bot: Bot | None = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=None))
    return _bot
