"""Bank bildirishnomalari Telegram orqali (telefonsiz).

Server admin ulagan Telegram akkaunt nomidan @HUMOcardbot, @CardXabarBot (va admin qo'shgan boshqa)
botlardagi yangi xabarlarni o'qiydi. Kirim xabari bo'lsa — p2p.register_incoming() ga beradi.

Xavfsizlik:
- akkaunt sessiyasi va API hash bazada shifrlangan holda saqlanadi (ENCRYPTION_KEY);
- faqat ro'yxatdagi bank botlari o'qiladi, boshqa chatlarga tegilmaydi, hech narsa yuborilmaydi;
- bir vaqtda faqat bitta jarayon ulanadi (pg advisory lock) — sessiya «dublikat» bo'lmasligi uchun.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import delete, select, text
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.errors import AppError
from app.models import AppSetting
from app.security import decrypt, encrypt
from app.services.notify import Outbox

log = logging.getLogger(__name__)

DEFAULT_BOTS = ["HUMOcardbot", "CardXabarBot"]
LOCK_ID = 7_201_002
K_SESSION, K_API_ID, K_API_HASH, K_ACCOUNT, K_BOTS = "_tg_session", "_tg_api_id", "_tg_api_hash", "_tg_account", "_tg_bots"
K_LAST = "_tg_last:"  # + bot nomi → oxirgi o'qilgan xabar id
K_SEEN = "_tg_seen:"  # + bot nomi → "iso|summa" (admin panel uchun)

_wake = asyncio.Event()
_state: dict = {"connected": False, "error": None, "generation": 0}
_login: dict = {}  # kod yuborilgandan keyingi vaqtinchalik holat (bitta jarayon)


def wake() -> None:
    """«To'ladim» bosilganda — darhol tekshirish."""
    _wake.set()


# ------------------------------------------------------------------ sozlamalar (app_settings jadvali)
async def _get_many(keys: list[str]) -> dict[str, str]:
    from app.db import SessionLocal

    async with SessionLocal() as s:
        rows = (await s.execute(select(AppSetting.key, AppSetting.value).where(AppSetting.key.in_(keys)))).all()
    return dict(rows)


async def _set(values: dict[str, str | None]) -> None:
    from app.db import SessionLocal

    async with SessionLocal() as s, s.begin():
        for k, v in values.items():
            if v is None:
                await s.execute(delete(AppSetting).where(AppSetting.key == k))
            else:
                await s.execute(insert(AppSetting).values(key=k, value=v)
                                .on_conflict_do_update(index_elements=["key"], set_={"value": v}))


def _clean_bot(name: str) -> str:
    name = name.strip().lstrip("@").split("/")[-1]
    if not name or not all(c.isalnum() or c == "_" for c in name) or len(name) > 64:
        raise AppError("bad_bot", f"Bot nomi noto'g'ri: {name or '—'}")
    return name


async def get_bots() -> list[str]:
    v = (await _get_many([K_BOTS])).get(K_BOTS)
    return [b for b in v.split(",") if b] if v is not None else list(DEFAULT_BOTS)


async def set_bots(bots: list[str]) -> list[str]:
    clean = list(dict.fromkeys(_clean_bot(b) for b in bots if b.strip()))[:10]
    await _set({K_BOTS: ",".join(clean)})
    wake()
    return clean


async def _api() -> tuple[int, str] | None:
    """API ID/hash: admin paneldan kiritilgan yoki Render'dagi TG_API_ID / TG_API_HASH."""
    d = await _get_many([K_API_ID, K_API_HASH])
    api_id = d.get(K_API_ID) or (str(settings.tg_api_id) if settings.tg_api_id else "")
    api_hash = decrypt(d.get(K_API_HASH)) if d.get(K_API_HASH) else settings.tg_api_hash
    if api_id.isdigit() and api_hash:
        return int(api_id), api_hash
    return None


async def status() -> dict:
    bots = await get_bots()
    d = await _get_many([K_SESSION, K_ACCOUNT, *(K_SEEN + b for b in bots)])
    seen = {}
    for b in bots:
        if v := d.get(K_SEEN + b):
            at, _, amount = v.partition("|")
            seen[b] = {"at": at, "amount": int(amount or 0)}
    return {
        "api_ready": await _api() is not None,
        "logged_in": bool(d.get(K_SESSION)),
        "account": d.get(K_ACCOUNT),
        "connected": _state["connected"],
        "error": _state["error"],
        "bots": bots,
        "seen": seen,
        "login_step": _login.get("step"),
    }


# ------------------------------------------------------------------ admin: akkauntni ulash
def _client(session_str: str, api: tuple[int, str]):
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    return TelegramClient(StringSession(session_str), api[0], api[1], receive_updates=False,
                          device_model="VAYNEXO server", app_version="1.0")


async def save_api(api_id: str, api_hash: str) -> None:
    api_id, api_hash = api_id.strip(), api_hash.strip()
    if not api_id.isdigit() or len(api_hash) != 32:
        raise AppError("bad_api", "API ID raqam, API hash esa 32 belgili bo'lishi kerak (my.telegram.org)")
    await _set({K_API_ID: api_id, K_API_HASH: encrypt(api_hash)})


async def send_code(phone: str) -> None:
    api = await _api()
    if not api:
        raise AppError("no_api", "Avval API ID va API hash kiriting")
    phone = "+" + "".join(c for c in phone if c.isdigit())
    if len(phone) < 10:
        raise AppError("bad_phone", "Telefon raqamini to'liq kiriting: +998 90 123 45 67")
    await _drop_login()
    client = _client("", api)
    await client.connect()
    try:
        sent = await client.send_code_request(phone)
    except Exception as e:  # noqa: BLE001
        await client.disconnect()
        raise AppError("tg_code", f"Kod yuborilmadi: {_tg_err(e)}") from None
    _login.update(step="code", phone=phone, hash=sent.phone_code_hash, client=client)


async def sign_in(code: str | None, password: str | None) -> dict:
    from telethon.errors import SessionPasswordNeededError

    client = _login.get("client")
    if not client:
        raise AppError("no_login", "Avval kod so'rang")
    try:
        if _login["step"] == "code":
            try:
                await client.sign_in(_login["phone"], (code or "").strip().replace(" ", ""), phone_code_hash=_login["hash"])
            except SessionPasswordNeededError:
                _login["step"] = "password"
                return {"need_password": True}
        else:
            await client.sign_in(password=password or "")
        me = await client.get_me()
        session_str = client.session.save()
    except AppError:
        raise
    except Exception as e:  # noqa: BLE001
        raise AppError("tg_login", f"Kirish bo'lmadi: {_tg_err(e)}") from None
    account = f"@{me.username}" if me.username else f"{me.first_name or ''} ···{(me.phone or '')[-4:]}".strip()
    await _drop_login()
    await _set({K_SESSION: encrypt(session_str), K_ACCOUNT: account})
    _state["generation"] += 1
    wake()
    return {"ok": True, "account": account}


async def logout() -> None:
    await _drop_login()
    d = await _get_many([K_SESSION])
    api = await _api()
    sess = decrypt(d.get(K_SESSION))
    await _set({K_SESSION: None, K_ACCOUNT: None})
    _state["generation"] += 1
    wake()
    if sess and api:  # sessiyani Telegram tomonida ham yopamiz
        try:
            await asyncio.sleep(2)  # ishlayotgan ulanish yopilsin
            c = _client(sess, api)
            await c.connect()
            await c.log_out()
        except Exception:  # noqa: BLE001
            log.warning("Telegram sessiyasi yopilmadi (allaqachon yopilgan bo'lishi mumkin)")


async def _drop_login() -> None:
    c = _login.pop("client", None)
    _login.clear()
    if c:
        try:
            await c.disconnect()
        except Exception:  # noqa: BLE001
            pass


def _tg_err(e: Exception) -> str:
    name = type(e).__name__
    return {
        "PhoneNumberInvalidError": "telefon raqami noto'g'ri",
        "PhoneCodeInvalidError": "kod noto'g'ri",
        "PhoneCodeExpiredError": "kod eskirgan, qayta so'rang",
        "PasswordHashInvalidError": "ikki bosqichli parol noto'g'ri",
        "FloodWaitError": f"juda ko'p urinish, {getattr(e, 'seconds', 60)} soniyadan keyin",
        "ApiIdInvalidError": "API ID / hash noto'g'ri",
        "PhoneNumberBannedError": "raqam Telegram tomonidan bloklangan",
    }.get(name, name)


# ------------------------------------------------------------------ xabarlarni qayta ishlash
async def process_messages(bot: str, messages: list) -> int:
    """Bank botidan kelgan yangi xabarlar (eskidan yangiga). Biriktirilganlar sonini qaytaradi."""
    from app.db import SessionLocal
    from app.services import p2p

    matched = 0
    for m in messages:
        raw = getattr(m, "message", None) or ""
        if getattr(m, "out", False) or not raw:
            continue
        amount = p2p.parse_bank_message(raw)
        if not amount:
            continue
        out = Outbox()
        async with SessionLocal() as s, s.begin():
            inc = await p2p.register_incoming(s, amount, "telegram", out, raw_text=raw[:1000], external_id=f"tg:{bot}:{m.id}")
        await out.flush()
        if inc is not None and inc.status == "matched":
            matched += 1
        await _set({K_SEEN + bot: f"{datetime.now(timezone.utc).isoformat()}|{amount}"})
    return matched


async def _active_topups() -> bool:
    from sqlalchemy import func

    from app.db import SessionLocal
    from app.models import Topup

    async with SessionLocal() as s:
        n = await s.scalar(select(func.count()).select_from(Topup).where(Topup.status.in_(("pending", "checking"))))
    return bool(n)


async def _poll(client) -> None:
    bots = await get_bots()
    d = await _get_many([K_LAST + b for b in bots])
    for bot in bots:
        try:
            last = int(d.get(K_LAST + bot) or 0)
            if last == 0:  # birinchi ulanish: eski tarix hisoblanmaydi
                msgs = await client.get_messages(bot, limit=1)
                if msgs:
                    await _set({K_LAST + bot: str(msgs[0].id)})
                continue
            msgs = list(reversed(await client.get_messages(bot, min_id=last, limit=50)))
            if msgs:
                await process_messages(bot, msgs)
                await _set({K_LAST + bot: str(max(m.id for m in msgs))})
        except Exception as e:  # noqa: BLE001 — bitta bot xatosi boshqalarini to'xtatmasin
            log.warning("Bank boti o'qilmadi (%s): %s", bot, e)
            _state["error"] = f"@{bot}: {_tg_err(e)}"


async def _sleep(seconds: float) -> None:
    try:
        await asyncio.wait_for(_wake.wait(), seconds)
    except asyncio.TimeoutError:
        pass
    _wake.clear()


async def run_forever() -> None:
    """Fon vazifasi: sessiya bo'lsa ulanadi va bank botlarini kuzatadi."""
    from app.db import engine

    while True:
        try:
            api = await _api()
            sess = decrypt((await _get_many([K_SESSION])).get(K_SESSION))
            if not (api and sess):
                _state.update(connected=False, error=None)
                await _sleep(60)
                continue
            async with engine.connect() as conn:
                if not await conn.scalar(text("SELECT pg_try_advisory_lock(:k)"), {"k": LOCK_ID}):
                    await conn.rollback()
                    await _sleep(20)  # boshqa jarayon ulangan (masalan, deploy paytida eski nusxa)
                    continue
                await conn.commit()
                try:
                    await _run_client(sess, api)
                finally:
                    await conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": LOCK_ID})
                    await conn.commit()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("Telegram bank kuzatuvi xatosi")
            _state.update(connected=False, error=_tg_err(e))
            await _sleep(60)


async def _run_client(sess: str, api: tuple[int, str]) -> None:
    gen = _state["generation"]
    client = _client(sess, api)
    await client.connect()
    try:
        if not await client.is_user_authorized():
            _state.update(connected=False, error="Sessiya yopilgan — akkauntni qaytadan ulang")
            await _set({K_SESSION: None})
            return
        _state.update(connected=True, error=None)
        log.info("Telegram bank kuzatuvi ishga tushdi")
        while _state["generation"] == gen:
            _state["error"] = None
            await _poll(client)
            await _sleep(8 if await _active_topups() else 45)
    finally:
        _state["connected"] = False
        await client.disconnect()
