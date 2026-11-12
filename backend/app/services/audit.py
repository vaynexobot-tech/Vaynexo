"""Admin harakatlari jurnali."""

import json
import logging
import re

from app.db import SessionLocal
from app.models import AdminLog

log = logging.getLogger(__name__)

SECRET_KEYS = {"api_hash", "password", "credentials", "pin", "secret", "number", "card_number"}

# yo'l → odam o'qiydigan nom
ACTIONS = [
    (r"/admin/users/(\d+)/balance$", "Balansni o'zgartirish"),
    (r"/admin/users/(\d+)/ban$", "Bloklash / blokdan chiqarish"),
    (r"/admin/incoming/\d+/to-user$", "Kirimni odamga yozish"),
    (r"/admin/incoming/\d+/assign$", "Kirimni so'rovga biriktirish"),
    (r"/admin/incoming/\d+/ignore$", "Kirimni e'tiborsiz qoldirish"),
    (r"/admin/incoming$", "Kirimni qo'lda kiritish"),
    (r"/admin/topups/\d+/confirm$", "«To'ladim» — tasdiqlash"),
    (r"/admin/topups/\d+/reject$", "«To'ladim» — rad etish"),
    (r"/admin/withdrawals/\d+", "Pul yechish"),
    (r"/admin/listings/\d+/moderate$", "E'lon moderatsiyasi"),
    (r"/admin/deals/\d+", "Nizo qarori"),
    (r"/admin/rent", "Ijara"),
    (r"/admin/donate", "Donat"),
    (r"/admin/tg", "TG buyurtma"),
    (r"/admin/boost", "Boost"),
    (r"/admin/kyc/(\d+)$", "Identifikatsiya"),
    (r"/admin/settings", "Sozlamalar"),
    (r"/admin/packages", "Donat paketlari"),
    (r"/admin/p2p-cards", "To'lov kartalari"),
    (r"/admin/tg-bank", "Bank botlari"),
    (r"/admin/promo", "Promo-kod"),
    (r"/admin/broadcast", "Ommaviy xabar"),
    (r"/admin/tournaments|/tournaments", "Turnir"),
    (r"/admin/partner", "Hamkor"),
    (r"/admin/matches", "Prognoz"),
]


def describe(path: str) -> tuple[str, int | None]:
    p = path.removeprefix("/api")
    for pat, name in ACTIONS:
        m = re.search(pat, p)
        if m:
            target = int(m.group(1)) if m.groups() and m.group(1) else None
            return name, target
    return p, None


def _clean(body: bytes, path: str = "") -> tuple[str, dict]:
    if not body:
        return "", {}
    try:
        data = json.loads(body[:5000])
    except (ValueError, UnicodeDecodeError):
        return "", {}
    if not isinstance(data, dict):
        return "", {}
    secret = SECRET_KEYS | ({"code"} if "tg-bank" in path else set())  # Telegram kirish kodi
    shown = {k: ("•••" if k in secret else ("ha" if v is True else "yo'q" if v is False else v)) for k, v in data.items() if k not in ("request_id",) and v not in (None, "")}
    return ", ".join(f"{k}: {v}" for k, v in shown.items())[:900], data


async def log_http(admin_id: int, method: str, path: str, body: bytes) -> None:
    name, target = describe(path)
    summary, data = _clean(body, path)
    amount = data.get("amount") if isinstance(data.get("amount"), int) else None
    target = target or (data.get("user_id") if isinstance(data.get("user_id"), int) else None)
    await write(admin_id, name, summary, amount, target)


async def write(admin_id: int, action: str, summary: str = "", amount: int | None = None, target_user: int | None = None) -> None:
    try:
        async with SessionLocal() as s, s.begin():
            s.add(AdminLog(admin_id=admin_id, action=action[:120], summary=summary[:1000], amount=amount, target_user=target_user))
    except Exception:  # noqa: BLE001 — jurnal yozilmasa ham asosiy amal buzilmasin
        log.exception("Admin jurnaliga yozib bo'lmadi")
