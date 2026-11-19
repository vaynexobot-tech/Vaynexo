"""MLBB ma'lumotlari va Arena o'yinlari: qahramonlar (rasmiy ro'yxat), «Qahramonni top» viktorinasi, haftaning qahramoni ovozi."""

import base64
import hashlib
import io
import json
import random
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.errors import AppError, BadState, NotFound
from app.models import HeroVote, QuizAnswer, User
from app.services import app_settings, arena

LANES = ("gold", "exp", "mid", "jungle", "roam")
RANKS = ("warrior", "elite", "master", "grandmaster", "epic", "legend", "mythic", "honor", "glory", "immortal")
ROLES = ("tank", "fighter", "assassin", "mage", "marksman", "support")
ROLE_UZ = {"tank": "Tank", "fighter": "Jangchi", "assassin": "Qotil", "mage": "Sehrgar", "marksman": "Mergan", "support": "Yordamchi"}
QUIZ_SIZE = 5  # kuniga savol: 3 ta «kim bu?», 2 ta «qaysi rol?»
QUIZ_WHO = 3


@lru_cache
def heroes() -> dict[int, dict]:
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "mlbb_heroes.json").read_text())
    return {h["id"]: h for h in data}


def valid_heroes(ids) -> list[int]:
    out: list[int] = []
    for x in ids or []:
        try:
            i = int(x)
        except (TypeError, ValueError):
            continue
        if i in heroes() and i not in out:
            out.append(i)
    return out[:3]


def _img_dir() -> Path | None:
    cands = []
    if settings.frontend_dir:
        cands.append(Path(settings.frontend_dir) / "mlbb" / "heroes")
    root = Path(__file__).resolve().parents[3]
    cands += [root / "frontend" / "dist" / "mlbb" / "heroes", root / "frontend" / "public" / "mlbb" / "heroes"]
    return next((c for c in cands if c.is_dir()), None)


# ---------------------------------------------------------------- MLBB kartasi
def profile_dict(u: User) -> dict:
    return {"nick": u.ml_nick or "", "lane": u.ml_lane or "", "rank": u.ml_rank or "", "heroes": u.ml_heroes or [],
            "ml_id": u.ml_id or "", "server": u.ml_server or "", "verified": bool(u.ml_verified), "region": u.ml_region or ""}


def update_profile(u: User, data: dict) -> None:
    lane = (data.get("lane") or "").lower()
    rank = (data.get("rank") or "").lower()
    if lane and lane not in LANES:
        raise AppError("bad_lane", "Liniya noto'g'ri")
    if rank and rank not in RANKS:
        raise AppError("bad_rank", "Rank noto'g'ri")
    u.ml_nick = (data.get("nick") or "").strip()[:32] or None
    u.ml_lane, u.ml_rank = lane or None, rank or None
    u.ml_heroes = valid_heroes(data.get("heroes"))
    if "region" in data:
        from app.services.teams import REGIONS

        reg = data.get("region") or ""
        if reg and reg not in REGIONS:
            raise AppError("bad_region", "Viloyat noto'g'ri")
        u.ml_region = reg or None


# ---------------------------------------------------------------- viktorina
def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _rng(user_id: int, day: str, n: int) -> random.Random:
    salt = f"{settings.p2p_secret}:{settings.bot_token}"
    seed = hashlib.sha256(f"quiz:{salt}:{user_id}:{day}:{n}".encode()).hexdigest()
    return random.Random(seed)


def question(user_id: int, day: str, n: int) -> dict:
    """Deterministik savol: javob mijozga yuborilmaydi, tekshiruvda qayta hisoblanadi."""
    rng = _rng(user_id, day, n)
    pool = sorted(heroes())
    # Kunning savollari bir-birini takrorlamasin
    picks = random.Random(f"{_rng(user_id, day, -1).random()}").sample(pool, QUIZ_SIZE)
    hid = picks[n]
    h = heroes()[hid]
    if n < QUIZ_WHO:
        others = rng.sample([x for x in pool if x != hid], 3)
        opts = [heroes()[x]["name"] for x in others] + [h["name"]]
        rng.shuffle(opts)
        return {"n": n, "type": "who", "hero": hid, "answer": h["name"], "options": opts}
    opts = list(ROLES)
    return {"n": n, "type": "role", "hero": hid, "answer": h["role"], "options": opts, "name": h["name"]}


def _image(q: dict, user_id: int, day: str) -> str | None:
    d = _img_dir()
    f = d / f"{q['hero']}.webp" if d else None
    if not f or not f.is_file():
        return None
    try:
        from PIL import Image

        img = Image.open(f).convert("RGB")
        if q["type"] == "who":  # kattalashtirilgan bo'lak — topish qiziqroq, rasm fayli bilan solishtirib bo'lmaydi
            rng = _rng(user_id, day, 100 + q["n"])
            w, h = img.size
            cw = int(w * rng.uniform(0.58, 0.72))
            x, y = rng.randint(0, w - cw), rng.randint(0, h - cw)
            img = img.crop((x, y, x + cw, y + cw))
        img = img.resize((192, 192), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=78)
        return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:  # noqa: BLE001
        return None


async def quiz(session: AsyncSession, user_id: int) -> dict:
    day = today()
    answered = {a.n: a.correct for a in await session.scalars(
        select(QuizAnswer).where(QuizAnswer.user_id == user_id, QuizAnswer.day == day))}
    pts = int(await app_settings.get_value(session, "pts_quiz"))
    qs = []
    for n in range(QUIZ_SIZE):
        q = question(user_id, day, n)
        item = {"n": n, "type": q["type"], "options": q["options"], "image": _image(q, user_id, day),
                "answered": n in answered, "correct": answered.get(n)}
        if q["type"] == "role":
            item["name"] = q["name"]
        if n in answered:  # javob berilgandan keyin to'g'risini ko'rsatamiz
            item["answer"] = q["answer"]
            item["hero"] = q["hero"]
        qs.append(item)
    right = sum(1 for v in answered.values() if v)
    return {"day": day, "points_each": pts, "questions": qs, "score": right, "done": len(answered) == QUIZ_SIZE,
            "roles": ROLE_UZ}


async def answer(session: AsyncSession, user_id: int, n: int, value: str) -> dict:
    if not 0 <= n < QUIZ_SIZE:
        raise NotFound("Savol")
    day = today()
    q = question(user_id, day, n)
    correct = (value or "").strip().lower() == str(q["answer"]).lower()
    try:
        async with session.begin_nested():
            session.add(QuizAnswer(user_id=user_id, day=day, n=n, correct=correct))
    except IntegrityError:
        raise BadState("Bu savolga javob berilgan") from None
    pts = 0
    if correct:
        pts = int(await app_settings.get_value(session, "pts_quiz"))
        await arena.add_points(session, user_id, pts, "quiz", f"quiz:{user_id}:{day}:{n}")
    await arena.bump(session, user_id, "quiz")
    return {"correct": correct, "answer": q["answer"], "hero": q["hero"], "points": pts}


# ---------------------------------------------------------------- haftaning qahramoni
def week() -> str:
    return arena.period_of("weekly")


async def vote_results(session: AsyncSession, user_id: int) -> dict:
    wk = week()
    rows = (await session.execute(select(HeroVote.hero_id, func.count()).where(HeroVote.week == wk)
                                  .group_by(HeroVote.hero_id).order_by(func.count().desc(), HeroVote.hero_id).limit(10))).all()
    total = await session.scalar(select(func.count()).select_from(HeroVote).where(HeroVote.week == wk)) or 0
    mine = await session.scalar(select(HeroVote.hero_id).where(HeroVote.week == wk, HeroVote.user_id == user_id))
    # O'tgan hafta g'olibi
    prev = await session.execute(select(HeroVote.hero_id, func.count()).where(HeroVote.week < wk)
                                 .group_by(HeroVote.week, HeroVote.hero_id).order_by(HeroVote.week.desc(), func.count().desc()).limit(1))
    p = prev.first()
    return {"week": wk, "total": total, "my": mine, "points": int(await app_settings.get_value(session, "pts_vote")),
            "top": [{"hero": h, "votes": c, "pct": round(c * 100 / total) if total else 0} for h, c in rows],
            "last_winner": p[0] if p else None}


async def vote(session: AsyncSession, user_id: int, hero_id: int) -> int:
    if hero_id not in heroes():
        raise NotFound("Qahramon")
    wk = week()
    try:
        async with session.begin_nested():
            session.add(HeroVote(user_id=user_id, week=wk, hero_id=hero_id))
    except IntegrityError:
        raise BadState("Bu hafta ovoz bergansiz") from None
    pts = int(await app_settings.get_value(session, "pts_vote"))
    await arena.add_points(session, user_id, pts, "hero_vote", f"vote:{user_id}:{wk}")
    await arena.bump(session, user_id, "hero_vote")
    return pts
