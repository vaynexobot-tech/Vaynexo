"""Telegram WebApp initData tekshiruvi va maxfiy ma'lumotlarni shifrlash."""

import hashlib
import hmac
import json
import os
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


# ---------------------------------------------------------------- PIN-kod
PIN_TOKEN_TTL = 12 * 3600


def _pin_secret() -> bytes:
    return hashlib.sha256(("pin:" + (settings.encryption_key or settings.bot_token or "dev")).encode()).digest()


def hash_secret(value: str) -> str:
    salt = os.urandom(16)
    h = hashlib.scrypt(value.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return salt.hex() + "$" + h.hex()


def check_secret(value: str, stored: str | None) -> bool:
    if not stored or "$" not in stored:
        return False
    salt_hex, h_hex = stored.split("$", 1)
    h = hashlib.scrypt(value.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=32)
    return hmac.compare_digest(h.hex(), h_hex)


def make_pin_token(user_id: int, pin_ver: int, ttl: int = PIN_TOKEN_TTL) -> str:
    exp = int(time.time()) + ttl
    msg = f"{user_id}.{pin_ver}.{exp}"
    sig = hmac.new(_pin_secret(), msg.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{msg}.{sig}"


def check_pin_token(token: str | None, user_id: int, pin_ver: int) -> bool:
    if not token:
        return False
    try:
        uid, ver, exp, sig = token.split(".")
        if int(uid) != user_id or int(ver) != pin_ver or int(exp) < time.time():
            return False
    except ValueError:
        return False
    calc = hmac.new(_pin_secret(), f"{uid}.{ver}.{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(calc, sig)
