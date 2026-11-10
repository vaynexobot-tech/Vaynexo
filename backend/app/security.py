"""Telegram WebApp initData tekshiruvi va maxfiy ma'lumotlarni shifrlash."""

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings

INIT_DATA_MAX_AGE = 24 * 3600


def validate_init_data(init_data: str, bot_token: str, max_age: int = INIT_DATA_MAX_AGE) -> dict | None:
    """https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app

    To'g'ri bo'lsa Telegram foydalanuvchi ma'lumotini (dict) qaytaradi, aks holda None.
    """
    if not init_data or not bot_token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        return None
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        return None
    check_string = "\n".join(f"{k}={pairs[k]}" for k in sorted(pairs))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calc = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc, received_hash):
        return None
    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        return None
    if max_age and time.time() - auth_date > max_age:
        return None
    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        return None
    if not isinstance(user, dict) or "id" not in user:
        return None
    user["start_param"] = pairs.get("start_param")
    return user


def _fernet() -> Fernet:
    key = settings.encryption_key
    if not key:
        raise RuntimeError("ENCRYPTION_KEY sozlanmagan")
    try:
        return Fernet(key.encode())
    except ValueError:
        # Fernet formatida bo'lmagan kalit (masalan, hosting yaratgan tasodifiy qiymat) — undan barqaror kalit hosil qilamiz
        import base64

        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))


def encrypt(text: str) -> str:
    return _fernet().encrypt(text.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None
