import os
import re
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- AI bo'limi (Claude) ---
    anthropic_api_key: str = ""  # bo'sh bo'lsa AI bo'limi o'chiq
    ai_model: str = "claude-opus-5-5"
    ai_daily_limit: int = 15  # bir foydalanuvchiga kuniga savollar

    # --- Telegram ---
    bot_token: str = ""
    bot_username: str = ""  # @ belgisisiz, masalan: vaynexo_bot
    webapp_url: str = "https://example.com"  # Mini App manzili (HTTPS)
    bot_webhook_url: str = ""  # bo'sh bo'lsa bot polling rejimida ishlaydi
    bot_webhook_secret: str = "change-me"
    admin_ids: Annotated[list[int], NoDecode] = []
    booster_group_id: int = 0  # boosterlar yopiq guruhi (chat id), 0 = o'chirilgan
    admin_chat_id: int = 0  # ogohlantirishlar yuboriladigan chat; 0 bo'lsa admin_ids ga yuboriladi

    # --- Infra ---
    database_url: str = "postgresql+asyncpg://postgres@localhost/vaynexo"
    db_null_pool: bool = False
    redis_url: str = "redis://localhost:6379/0"  # bo'sh bo'lsa — yengil rejim (Redis'siz, bitta jarayon)
    frontend_dir: str = ""  # yig'ilgan frontend (frontend/dist) — berilsa API o'zi beradi
    media_dir: str = "media"
    media_url: str = "/media"
    encryption_key: str = ""  # Fernet kaliti: akkaunt parollari shifrlanadi
    dev_mode: bool = False  # True bo'lsa X-Dev-User sarlavhasi bilan brauzerda sinash mumkin
    cors_origins: Annotated[list[str], NoDecode] = ["*"]

    # --- P2P to'ldirish ---
    p2p_card_number: str = "8600 0000 0000 0000"
    p2p_card_holder: str = "VAYNEXO"
    p2p_secret: str = "change-me"
    tg_api_id: int = 0  # bank botlarini o'qish uchun (my.telegram.org); admin paneldan ham kiritsa bo'ladi
    tg_api_hash: str = ""  # SMS-forwarder /api/p2p/incoming uchun
    topup_min: int = 1_000
    topup_max: int = 20_000_000
    topup_ttl_minutes: int = 30
    topup_late_match_hours: int = 24  # muddati o'tgan bo'lsa ham shu vaqt ichida kirim topilsa hisoblanadi

    # --- Biznes qoidalari ---
    commission_percent: int = 5  # akkaunt savdosidan platforma ulushi
    withdraw_min: int = 10_000
    escrow_auto_release_hours: int = 48
    referral_bonus: int = 1234  # boshlang'ich qiymat; keyin admin paneldan o'zgartiriladi (0 = o'chiq)
    stars_rate: int = 220  # 1 Star narxi (so'm)

    # --- Donat provayder ---
    donate_provider: str = "manual"  # manual | http | mock (faqat DEV_MODE)
    donate_provider_url: str = ""
    donate_provider_key: str = ""

    @field_validator("admin_ids", "cors_origins", mode="before")
    @classmethod
    def _split(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                import json

                return json.loads(v)
            return [x.strip() for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return v

    @field_validator("database_url", mode="after")
    @classmethod
    def _asyncpg_url(cls, v: str) -> str:
        """Render/Heroku kabi xizmatlar `postgres://...` beradi — asyncpg drayveriga moslaymiz."""
        v = re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", v)
        return re.sub(r"[?&]sslmode=[^&]*", "", v)

    @field_validator("bot_webhook_secret", mode="after")
    @classmethod
    def _webhook_secret(cls, v: str) -> str:
        # Telegram faqat A-Z a-z 0-9 _ - belgilariga ruxsat beradi
        return re.sub(r"[^A-Za-z0-9_-]", "", v)[:256] or "change-me"

    @model_validator(mode="after")
    def _platform_defaults(self):
        # Webhook kaliti berilmasa, standart "change-me" taxmin qilinadi — bot tokenidan barqaror kalit hosil qilamiz
        if self.bot_webhook_secret == "change-me" and self.bot_token:
            import hashlib

            self.bot_webhook_secret = hashlib.sha256(("wh:" + self.bot_token).encode()).hexdigest()[:64]
        # Render saytning tashqi manzilini RENDER_EXTERNAL_URL orqali beradi
        ext = os.environ.get("RENDER_EXTERNAL_URL", "").rstrip("/")
        if ext:
            if self.webapp_url == "https://example.com":
                self.webapp_url = ext
            if not self.bot_webhook_url:
                self.bot_webhook_url = ext
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
