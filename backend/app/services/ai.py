"""AI bo'limi: Claude savolni tushunadi, bazadan mos akkauntlarni topamiz.

Bitta so'rov: Claude javob matni va qidiruv filtrlarini JSON ko'rinishida qaytaradi (structured output),
keyin filtrlar bo'yicha e'lonlarni o'zimiz bazadan olamiz — model e'lonlarni o'ylab topa olmaydi.
"""

import json
import logging
from datetime import datetime, timezone

import anthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.errors import AppError
from app.models import Listing

log = logging.getLogger(__name__)

RANKS = ["Epic", "Legend", "Mythic", "Mythic Honor", "Mythic Glory", "Mythic Immortal"]
LANG_NAME = {"uz": "o'zbek (lotin)", "ru": "rus", "en": "ingliz"}

SYSTEM = """Sen VAYNEXO — Telegram'dagi o'yin bozorining yordamchisisan (Mobile Legends va Magic Chess).
Bo'limlar: Almaz donat (ML/MC, 1–5 daqiqada), Account savdo (garant bilan), Account ijara (12 soat, 24 soat, 3 kun, 1 hafta; depozit qaytariladi),
Boost (rank ko'tarish, Express va qo'shimcha tanlovlar), TG xizmatlar (Premium, Stars, Gift, NFT), Arena (turnirlar), Top 100.
Hamyon kartaga P2P o'tkazma bilan to'ldiriladi: tizim bergan ANIQ summani o'tkazish kerak, 1–3 daqiqada tushadi.
Pul yechish: Hamyon → Yechish, 24 soat ichida. Muammo bo'lsa: @vaynexo_support.
Narxlar so'mda (UZS). "500k" = 500 000, "1.2 mln" = 1 200 000.

Qoidalar:
- Foydalanuvchi akkaunt qidirsa (rank, skin soni, narx, o'yin), search=true qil va filtrlarni to'ldir; reply — qisqa kirish gapi
  (masalan: "Talablaringizga mos e'lonlar:"), e'lonlarni o'zing o'ylab topma, ularni tizim bazadan qo'shadi.
- Boshqa savollarga (to'ldirish, garant, boost va h.k.) search=false va reply'da 1–4 gapda aniq javob ber.
- VAYNEXO'ga aloqasi yo'q savollarga muloyim rad javob ber.
- Filtr qo'yilmasa: min_skins=0, min_price=0, max_price=0 (0 = cheklov yo'q), game="any", ranks=[].
- Rank nomlari faqat shulardan: """ + ", ".join(RANKS) + "."

SCHEMA = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "search": {"type": "boolean"},
        "game": {"type": "string", "enum": ["ML", "MC", "any"]},
        "ranks": {"type": "array", "items": {"type": "string", "enum": RANKS}},
        "min_skins": {"type": "integer"},
        "min_price": {"type": "integer"},
        "max_price": {"type": "integer"},
        "sort": {"type": "string", "enum": ["best", "cheap", "skins", "new"]},
    },
    "required": ["reply", "search", "game", "ranks", "min_skins", "min_price", "max_price", "sort"],
    "additionalProperties": False,
}

_client: anthropic.AsyncAnthropic | None = None


def client() -> anthropic.AsyncAnthropic:
    global _client
    if not settings.anthropic_api_key:
        raise AppError("ai_off", "AI bo'limi hali ulanmagan. Tez orada ishga tushadi", 503)
    if _client is None:
        _client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key, timeout=40.0, max_retries=1)
    return _client


async def _call(system: str, messages: list[dict], schema: dict, max_tokens: int = 2000) -> dict:
    try:
        resp = await client().beta.messages.create(
            model=settings.ai_model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError as e:
        raise AppError("ai_busy", "AI hozir band. Bir daqiqadan so'ng urinib ko'ring", 429) from e
    except anthropic.AuthenticationError as e:
        log.error("ANTHROPIC_API_KEY noto'g'ri")
        raise AppError("ai_off", "AI bo'limi hali ulanmagan. Tez orada ishga tushadi", 503) from e
    except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
        log.warning("AI xatosi: %s", e)
        raise AppError("ai_error", "AI javob bera olmadi. Qayta urinib ko'ring", 502) from e
    if resp.stop_reason == "refusal":
        return {}
    if resp.stop_reason == "max_tokens":
        raise AppError("ai_error", "AI javob bera olmadi. Qayta urinib ko'ring", 502)
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AppError("ai_error", "AI javob bera olmadi. Qayta urinib ko'ring", 502) from e


async def find_listings(session: AsyncSession, f: dict, limit: int = 3) -> list[Listing]:
    q = select(Listing).where(Listing.status == "active").options(selectinload(Listing.seller))
    if f.get("game") in ("ML", "MC"):
        q = q.where(Listing.game == f["game"])
    ranks = [r for r in f.get("ranks") or [] if r in RANKS]
    if ranks:
        q = q.where(func.lower(Listing.rank).in_([r.lower() for r in ranks]))
    if (f.get("min_skins") or 0) > 0:
        q = q.where(Listing.skins >= f["min_skins"])
    if (f.get("min_price") or 0) > 0:
        q = q.where(Listing.price >= f["min_price"])
    if (f.get("max_price") or 0) > 0:
        q = q.where(Listing.price <= f["max_price"])
    order = {
        "cheap": [Listing.price.asc()],
        "skins": [Listing.skins.desc()],
        "new": [Listing.id.desc()],
    }.get(f.get("sort"), [Listing.skins.desc(), Listing.price.asc()])
    vip_first = (Listing.vip_until > datetime.now(timezone.utc)).desc().nulls_last()
    return list(await session.scalars(q.order_by(vip_first, *order).limit(limit)))


async def ask(session: AsyncSession, lang: str, question: str, history: list[dict]) -> tuple[str, list[Listing]]:
    msgs = []
    for h in history[-6:]:
        role = "assistant" if h.get("role") == "ai" else "user"
        text = str(h.get("text") or "")[:600]
        if text and (not msgs or msgs[-1]["role"] != role):
            msgs.append({"role": role, "content": text})
    if msgs and msgs[0]["role"] == "assistant":
        msgs.pop(0)
    if msgs and msgs[-1]["role"] == "user":
        msgs.pop()
    msgs.append({"role": "user", "content": question})
    system = SYSTEM + f"\nJavob tili: {LANG_NAME.get(lang, LANG_NAME['uz'])}."
    data = await _call(system, msgs, SCHEMA)
    if not data:
        return NO_ANSWER.get(lang, NO_ANSWER["uz"]), []
    reply = (data.get("reply") or "").strip()[:800]
    if not data.get("search"):
        return reply, []
    items = await find_listings(session, data)
    if not items:
        return NOTHING.get(lang, NOTHING["uz"]), []
    return reply, items


NOTHING = {
    "uz": "Afsuski, hozir bunday e'lon topilmadi. Talablarni biroz yumshatib ko'ring (masalan, narx yoki skin soni).",
    "ru": "К сожалению, сейчас таких объявлений нет. Попробуйте смягчить требования (цену или количество скинов).",
    "en": "Sorry, no matching listings right now. Try relaxing the requirements (price or number of skins).",
}
NO_ANSWER = {
    "uz": "Bu savolga javob bera olmayman. VAYNEXO bo'yicha savol bering.",
    "ru": "Не могу ответить на этот вопрос. Спросите что-нибудь о VAYNEXO.",
    "en": "I can't answer that. Please ask something about VAYNEXO.",
}

DESC_SCHEMA = {
    "type": "object",
    "properties": {"title": {"type": "string"}, "description": {"type": "string"}},
    "required": ["title", "description"],
    "additionalProperties": False,
}


async def describe_listing(lang: str, fields: dict, notes: str) -> dict:
    """«AI bilan to'ldirish»: e'lon sarlavhasi va tavsifini yozib beradi."""
    system = (
        "Sen o'yin akkaunti sotuvchisiga e'lon yozib berasan. Faqat berilgan ma'lumotlardan foydalan, o'ylab topma. "
        "Login, parol, pochta yoki telefon yozma. Sarlavha 60 belgigacha (masalan: «Mythic akkaunt · 120 skin»), "
        "tavsif 2–5 qisqa gap, sotuvchi nomidan, reklama uslubida emas, aniq. "
        f"Til: {LANG_NAME.get(lang, LANG_NAME['uz'])}."
    )
    content = "Ma'lumotlar: " + json.dumps(fields, ensure_ascii=False) + (f"\nSotuvchi izohi: {notes}" if notes else "")
    data = await _call(system, [{"role": "user", "content": content}], DESC_SCHEMA, max_tokens=1500)
    if not data:
        raise AppError("ai_error", "AI javob bera olmadi. Qayta urinib ko'ring", 502)
    return {"title": data["title"].strip()[:120], "description": data["description"].strip()[:2000]}
