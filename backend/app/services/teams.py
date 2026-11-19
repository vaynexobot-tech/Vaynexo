"""Qidiruv: 5v5 bahs (scrim), 1v1 duel, rankedga sherik, jamoa topish; jamoalar, so'rov/taklif, hurmat, sherik signali."""

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, BadState, Forbidden, NotFound
from app.models import PartnerSignal, PlayerContact, PlayerRating, Team, TeamMember, TeamPost, TeamRequest, User
from app.services.mlbb import RANKS, valid_heroes
from app.services.notify import Outbox, webapp_button

KINDS = ("player", "team", "duo", "duel", "scrim")
LANES = ("Gold", "Mid", "EXP", "Jungle", "Roam")
REGIONS = (
    "Toshkent sh.", "Toshkent vil.", "Andijon", "Buxoro", "Farg'ona", "Jizzax", "Xorazm", "Namangan", "Navoiy",
    "Qashqadaryo", "Qoraqalpog'iston", "Samarqand", "Sirdaryo", "Surxondaryo",
)
TEAM_MAX = 7  # 5 asosiy + 2 zaxira
POST_DAYS = {"duo": 2, "duel": 2, "scrim": 3, "player": 7, "team": 7}
KIND_UZ = {"player": "jamoa qidirmoqda", "team": "o'yinchi qidirmoqda", "duo": "rankedga sherik", "duel": "1v1 duel", "scrim": "5v5 bahs"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def rank_idx(r: str | None) -> int:
    r = (r or "").lower()
    for i, k in enumerate(RANKS):
        if k == r:
            return i
    for i, k in reversed(list(enumerate(RANKS))):  # «Mythic Glory», «M. Honor» kabi matnlar
        if k in r:
            return i
    return -1


def close_rank(a: str | None, b: str | None) -> bool:
    ia, ib = rank_idx(a), rank_idx(b)
    return ia < 0 or ib < 0 or abs(ia - ib) <= 1


# ---------------------------------------------------------------- hurmat va bog'lanishlar
async def add_contact(session: AsyncSession, a: int, b: int) -> None:
    if a == b:
        return
    lo, hi = min(a, b), max(a, b)
    if await session.scalar(select(PlayerContact.id).where(PlayerContact.a_id == lo, PlayerContact.b_id == hi)):
        return
    try:
        async with session.begin_nested():
            session.add(PlayerContact(a_id=lo, b_id=hi))
    except IntegrityError:
        pass


async def respect_of(session: AsyncSession, user_ids: set[int]) -> dict[int, dict]:
    if not user_ids:
        return {}
    rows = (await session.execute(select(PlayerRating.target_id, PlayerRating.good, func.count())
                                  .where(PlayerRating.target_id.in_(user_ids)).group_by(PlayerRating.target_id, PlayerRating.good))).all()
    out: dict[int, dict] = {u: {"good": 0, "bad": 0} for u in user_ids}
    for uid, good, n in rows:
        out[uid]["good" if good else "bad"] += n
    for v in out.values():
        total = v["good"] + v["bad"]
        v["pct"] = round(v["good"] * 100 / total) if total else None
        v["toxic"] = v["bad"] >= 3 and v["bad"] > v["good"]
    return out


async def rate(session: AsyncSession, rater: int, target: int, good: bool) -> dict:
    if rater == target:
        raise BadState("O'zingizni baholab bo'lmaydi")
    lo, hi = min(rater, target), max(rater, target)
    if not await session.scalar(select(PlayerContact.id).where(PlayerContact.a_id == lo, PlayerContact.b_id == hi)):
        raise BadState("Faqat bog'langan (birga o'ynagan) o'yinchini baholash mumkin")
    r = await session.scalar(select(PlayerRating).where(PlayerRating.rater_id == rater, PlayerRating.target_id == target))
    if r:
        r.good = good
    else:
        session.add(PlayerRating(rater_id=rater, target_id=target, good=good))
    await session.flush()
    return (await respect_of(session, {target}))[target]


async def my_contacts(session: AsyncSession, uid: int) -> list[dict]:
    rows = list(await session.scalars(select(PlayerContact).where(or_(PlayerContact.a_id == uid, PlayerContact.b_id == uid))
                                      .order_by(PlayerContact.id.desc()).limit(50)))
    ids = {r.b_id if r.a_id == uid else r.a_id for r in rows}
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_(ids or {0})))}
    mine = {r.target_id: r.good for r in await session.scalars(select(PlayerRating).where(PlayerRating.rater_id == uid, PlayerRating.target_id.in_(ids or {0})))}
    resp = await respect_of(session, ids)
    return [{**card(users[i]), "my_rating": mine.get(i), "respect": resp.get(i)} for i in ids if i in users]


# ---------------------------------------------------------------- kartalar
def card(u: User) -> dict:
    return {"user_id": u.id, "nick": u.ml_nick or u.username or u.first_name, "rank": u.ml_rank or "", "lane": u.ml_lane or "",
            "heroes": u.ml_heroes or [], "region": u.ml_region or "", "verified": bool(u.ml_verified)}


async def _team_of(session: AsyncSession, uid: int) -> Team | None:
    tid = await session.scalar(select(TeamMember.team_id).where(TeamMember.user_id == uid))
    return await session.get(Team, tid) if tid else None


async def team_dict(session: AsyncSession, t: Team, full: bool = False, me: int | None = None) -> dict:
    members = list(await session.scalars(select(TeamMember).where(TeamMember.team_id == t.id).order_by(TeamMember.id)))
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_([m.user_id for m in members] or [0])))}
    idx = [rank_idx(users[m.user_id].ml_rank) for m in members if m.user_id in users and rank_idx(users[m.user_id].ml_rank) >= 0]
    avg = RANKS[round(sum(idx) / len(idx))] if idx else ""
    cap = users.get(t.captain_id)
    d = {"id": t.id, "name": t.name, "tag": t.tag, "region": t.region, "about": t.about, "is_open": t.is_open,
         "captain": (cap.ml_nick or cap.username or cap.first_name) if cap else "", "captain_id": t.captain_id,
         "members": len(members), "max": TEAM_MAX, "free": max(0, TEAM_MAX - len(members)), "avg_rank": avg}
    if full:
        resp = await respect_of(session, set(users))
        d["roster"] = [{**card(users[m.user_id]), "role": m.role, "respect": resp.get(m.user_id)} for m in members if m.user_id in users]
        if me is not None:
            d["is_member"] = any(m.user_id == me for m in members)
            d["is_captain"] = t.captain_id == me
            d["my_request"] = await session.scalar(select(TeamRequest.status).where(
                TeamRequest.team_id == t.id, TeamRequest.user_id == me, TeamRequest.kind == "join", TeamRequest.status == "pending"))
    return d


# ---------------------------------------------------------------- jamoalar
def _clean_name(name: str) -> str:
    name = re.sub(r"\s+", " ", (name or "").strip())
    if not 2 <= len(name) <= 32:
        raise AppError("bad_name", "Jamoa nomi 2–32 belgi bo'lsin")
    return name


async def create_team(session: AsyncSession, uid: int, data: dict) -> Team:
    if await _team_of(session, uid):
        raise BadState("Siz allaqachon jamoadasiz — avval undan chiqing")
    name = _clean_name(data.get("name", ""))
    if await session.scalar(select(Team.id).where(func.lower(Team.name) == name.lower(), Team.status == "active")):
        raise BadState("Bu nomli jamoa bor — boshqa nom tanlang")
    tag = re.sub(r"[^A-Za-z0-9]", "", data.get("tag") or "")[:6].upper() or name[:3].upper()
    region = data.get("region") or ""
    if region and region not in REGIONS:
        raise AppError("bad_region", "Viloyat noto'g'ri")
    t = Team(name=name, tag=tag, captain_id=uid, region=region, about=(data.get("about") or "").strip()[:200], is_open=bool(data.get("is_open", True)))
    session.add(t)
    await session.flush()
    session.add(TeamMember(team_id=t.id, user_id=uid, role="captain"))
    await session.flush()
    return t


async def list_teams(session: AsyncSession, q: str = "", open_only: bool = False, limit: int = 50) -> list[dict]:
    stmt = select(Team).where(Team.status == "active")
    if q.strip():
        like = f"%{q.strip()[:32]}%"
        stmt = stmt.where(or_(Team.name.ilike(like), Team.tag.ilike(like)))
    teams = list(await session.scalars(stmt.order_by(Team.id.desc()).limit(200)))
    out = [await team_dict(session, t) for t in teams]
    if open_only:
        out = [x for x in out if x["free"] > 0 and x["is_open"]]
    return out[:limit]


async def request_join(session: AsyncSession, uid: int, team_id: int, out: Outbox) -> TeamRequest:
    t = await session.get(Team, team_id)
    if t is None or t.status != "active":
        raise NotFound("Jamoa")
    if await _team_of(session, uid):
        raise BadState("Siz allaqachon jamoadasiz")
    if not t.is_open:
        raise BadState("Jamoa yangi a'zo qabul qilmayapti")
    if (await team_dict(session, t))["free"] <= 0:
        raise BadState("Jamoada bo'sh joy yo'q")
    dup = await session.scalar(select(TeamRequest).where(TeamRequest.team_id == t.id, TeamRequest.user_id == uid,
                                                         TeamRequest.status == "pending"))
    if dup:
        raise BadState("So'rov allaqachon yuborilgan")
    r = TeamRequest(team_id=t.id, user_id=uid, kind="join")
    session.add(r)
    await session.flush()
    u = await session.get(User, uid)
    out.user(t.captain_id, f"📨 «{t.name}» jamoasiga qo'shilish so'rovi: {card(u)['nick']}"
             + (f" · {u.ml_rank.title()}" if u.ml_rank else "") + (f" · {u.ml_lane}" if u.ml_lane else ""),
             webapp_button("Ko'rib chiqish", "/arena"))
    return r


async def invite(session: AsyncSession, captain: int, user_id: int, out: Outbox) -> TeamRequest:
    t = await _team_of(session, captain)
    if t is None or t.captain_id != captain:
        raise Forbidden("Faqat jamoa sardori taklif yubora oladi")
    if user_id == captain:
        raise BadState("O'zingizni taklif qila olmaysiz")
    if await _team_of(session, user_id):
        raise BadState("Bu o'yinchi allaqachon jamoada")
    if (await team_dict(session, t))["free"] <= 0:
        raise BadState("Jamoada bo'sh joy yo'q")
    if await session.scalar(select(TeamRequest.id).where(TeamRequest.team_id == t.id, TeamRequest.user_id == user_id,
                                                         TeamRequest.status == "pending")):
        raise BadState("Taklif allaqachon yuborilgan")
    r = TeamRequest(team_id=t.id, user_id=user_id, kind="invite")
    session.add(r)
    await session.flush()
    await add_contact(session, captain, user_id)
    out.user(user_id, f"🤝 «{t.name}» [{t.tag}] jamoasi sizni taklif qilmoqda!", webapp_button("Taklifni ko'rish", "/arena"))
    return r


async def answer_request(session: AsyncSession, uid: int, rid: int, accept: bool, out: Outbox) -> TeamRequest:
    r = await session.get(TeamRequest, rid, with_for_update=True)
    if r is None or r.status != "pending":
        raise NotFound("So'rov")
    t = await session.get(Team, r.team_id)
    # join — sardor javob beradi; invite — taklif qilingan o'yinchi
    if (r.kind == "join" and t.captain_id != uid) or (r.kind == "invite" and r.user_id != uid):
        raise Forbidden()
    if not accept:
        r.status = "declined"
        out.user(r.user_id if r.kind == "join" else t.captain_id,
                 f"«{t.name}»: " + ("so'rovingiz rad etildi" if r.kind == "join" else "taklifingiz rad etildi"))
        return r
    if await _team_of(session, r.user_id):
        r.status = "cancelled"
        raise BadState("O'yinchi allaqachon boshqa jamoada")
    if (await team_dict(session, t))["free"] <= 0:
        raise BadState("Jamoada bo'sh joy yo'q")
    r.status = "accepted"
    session.add(TeamMember(team_id=t.id, user_id=r.user_id, role="member"))
    await add_contact(session, t.captain_id, r.user_id)
    # Shu o'yinchining boshqa kutilayotgan so'rov/takliflari bekor
    for o in await session.scalars(select(TeamRequest).where(TeamRequest.user_id == r.user_id, TeamRequest.status == "pending", TeamRequest.id != r.id)):
        o.status = "cancelled"
    await session.flush()
    out.user(r.user_id, f"✅ Siz «{t.name}» jamoasiga qo'shildingiz!", webapp_button("Jamoam", "/arena"))
    if r.kind == "invite":
        out.user(t.captain_id, f"✅ Taklifingiz qabul qilindi — yangi a'zo «{t.name}» jamoasida")
    return r


async def leave(session: AsyncSession, uid: int) -> None:
    m = await session.scalar(select(TeamMember).where(TeamMember.user_id == uid).with_for_update())
    if m is None:
        raise BadState("Siz jamoada emassiz")
    t = await session.get(Team, m.team_id, with_for_update=True)
    await session.delete(m)
    await session.flush()
    if t.captain_id == uid:
        nxt = await session.scalar(select(TeamMember).where(TeamMember.team_id == t.id).order_by(TeamMember.id).limit(1))
        if nxt:
            t.captain_id, nxt.role = nxt.user_id, "captain"
        else:
            t.status = "deleted"
            t.name = f"{t.name}#{t.id}"[:32]  # nomni bo'shatamiz


async def kick(session: AsyncSession, captain: int, user_id: int, out: Outbox) -> None:
    t = await _team_of(session, captain)
    if t is None or t.captain_id != captain:
        raise Forbidden("Faqat sardor chiqara oladi")
    m = await session.scalar(select(TeamMember).where(TeamMember.team_id == t.id, TeamMember.user_id == user_id))
    if m is None or user_id == captain:
        raise NotFound("A'zo")
    await session.delete(m)
    out.user(user_id, f"«{t.name}» jamoasidan chiqarildingiz")


async def update_team(session: AsyncSession, captain: int, data: dict) -> Team:
    t = await _team_of(session, captain)
    if t is None or t.captain_id != captain:
        raise Forbidden("Faqat sardor o'zgartira oladi")
    if "is_open" in data:
        t.is_open = bool(data["is_open"])
    if data.get("region") is not None:
        if data["region"] and data["region"] not in REGIONS:
            raise AppError("bad_region", "Viloyat noto'g'ri")
        t.region = data["region"]
    if data.get("about") is not None:
        t.about = data["about"].strip()[:200]
    return t


async def my_team(session: AsyncSession, uid: int) -> dict:
    t = await _team_of(session, uid)
    out: dict = {"team": await team_dict(session, t, full=True, me=uid) if t else None, "requests": [], "invites": []}
    if t and t.captain_id == uid:
        reqs = list(await session.scalars(select(TeamRequest).where(TeamRequest.team_id == t.id, TeamRequest.kind == "join",
                                                                    TeamRequest.status == "pending").order_by(TeamRequest.id)))
        users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_([r.user_id for r in reqs] or [0])))}
        resp = await respect_of(session, set(users))
        out["requests"] = [{"id": r.id, **card(users[r.user_id]), "respect": resp.get(r.user_id)} for r in reqs if r.user_id in users]
    if not t:
        inv = list(await session.scalars(select(TeamRequest).where(TeamRequest.user_id == uid, TeamRequest.kind == "invite",
                                                                   TeamRequest.status == "pending").order_by(TeamRequest.id.desc())))
        for r in inv:
            team = await session.get(Team, r.team_id)
            if team and team.status == "active":
                out["invites"].append({"id": r.id, "team": await team_dict(session, team)})
    return out


# ---------------------------------------------------------------- e'lonlar
async def create_post(session: AsyncSession, uid: int, data: dict, out: Outbox) -> TeamPost:
    kind = data.get("kind")
    if kind not in KINDS:
        raise AppError("bad_kind", "E'lon turi noto'g'ri")
    u = await session.get(User, uid)
    team = await _team_of(session, uid)
    if kind in ("team", "scrim"):
        if team is None or team.captain_id != uid:
            raise BadState("Bu e'lonni jamoa sardori beradi — avval jamoa tuzing")
        if kind == "team" and (await team_dict(session, team))["free"] <= 0:
            raise BadState("Jamoada bo'sh joy yo'q")
    if kind == "player" and team:
        raise BadState("Siz allaqachon jamoadasiz")
    lane = data.get("lane") or ""
    if lane and lane not in LANES:
        raise AppError("bad_lane", "Liniya noto'g'ri")
    region = data.get("region") or u.ml_region or ""
    if region and region not in REGIONS:
        region = ""
    active = await session.scalar(select(func.count()).select_from(TeamPost).where(
        TeamPost.user_id == uid, TeamPost.kind == kind, TeamPost.status == "active", TeamPost.expires_at > _now()))
    if active >= 2:
        raise AppError("too_many", "Bu turdagi 2 tadan ko'p faol e'lon bo'lmaydi")
    name = (team.name if kind in ("team", "scrim") else (data.get("name") or u.ml_nick or u.username or u.first_name or "")).strip()[:64]
    rank = (data.get("rank") or u.ml_rank or "").strip()[:32]
    p = TeamPost(user_id=uid, kind=kind, name=name or "—", lane=lane, rank=rank, online=(data.get("online") or "").strip()[:32],
                 note=(data.get("note") or "").strip()[:300], heroes=valid_heroes(data.get("heroes") or u.ml_heroes or []),
                 region=region, team_id=team.id if kind in ("team", "scrim") else None,
                 expires_at=_now() + timedelta(days=POST_DAYS[kind]))
    session.add(p)
    await session.flush()
    if kind == "duo":
        await _signal(session, p, u, out)
    return p


async def _signal(session: AsyncSession, p: TeamPost, author: User, out: Outbox) -> None:
    """Sherik signali: rankingi mos obunachilarga xabar (ko'pi bilan 50 ta)."""
    subs = list(await session.scalars(select(User).join(PartnerSignal, PartnerSignal.user_id == User.id)
                                      .where(PartnerSignal.enabled.is_(True), User.id != author.id).limit(500)))
    n = 0
    for s in subs:
        if s.ml_rank and close_rank(s.ml_rank, p.rank or author.ml_rank):
            out.user(s.id, f"🔔 Sherik signali: {p.name} rankedga sherik qidirmoqda"
                     + (f" · {p.rank.title()}" if p.rank else "") + (f" · {p.lane}" if p.lane else "")
                     + (f" · {p.online}" if p.online else ""), webapp_button("Ko'rish", "/arena"))
            n += 1
            if n >= 50:
                break


async def list_posts(session: AsyncSession, me: User, kind: str, lane: str = "", region: str = "", match: bool = False) -> list[dict]:
    q = select(TeamPost).where(TeamPost.status == "active", TeamPost.expires_at > _now(), TeamPost.kind == kind)
    if lane in LANES:
        q = q.where(TeamPost.lane == lane)
    if region in REGIONS:
        q = q.where(TeamPost.region == region)
    rows = list(await session.scalars(q.order_by(TeamPost.id.desc()).limit(100)))
    users = {u.id: u for u in await session.scalars(select(User).where(User.id.in_({p.user_id for p in rows} or {0})))}
    resp = await respect_of(session, set(users))
    teams = {t.id: t for t in await session.scalars(select(Team).where(Team.id.in_({p.team_id for p in rows if p.team_id} or {0})))}
    out = []
    for p in rows:
        u = users.get(p.user_id)
        rank = p.rank or (u.ml_rank if u else "")
        if match and me.ml_rank and not close_rank(me.ml_rank, rank):
            continue
        d = {"id": p.id, "kind": p.kind, "name": p.name, "lane": p.lane, "rank": rank, "online": p.online, "note": p.note,
             "heroes": p.heroes or [], "region": p.region, "mine": p.user_id == me.id, "created_at": p.created_at.isoformat() if p.created_at else None,
             "author": card(u) if u else None, "respect": resp.get(p.user_id)}
        if p.team_id and p.team_id in teams:
            d["team"] = await team_dict(session, teams[p.team_id])
        out.append(d)
    return out


async def respond(session: AsyncSession, me: User, pid: int, out: Outbox) -> dict:
    p = await session.get(TeamPost, pid)
    if p is None or p.status != "active" or p.expires_at < _now():
        raise NotFound("E'lon")
    if p.user_id == me.id:
        raise BadState("Bu sizning e'loningiz")
    who = f"@{me.username}" if me.username else (me.ml_nick or me.first_name)
    info = card(me)
    extra = " · ".join(x for x in [info["rank"].title(), info["lane"], info["region"]] if x)
    if p.kind == "team":  # jamoa o'yinchi qidirmoqda → qo'shilish so'rovi
        r = await request_join(session, me.id, p.team_id, out)
        await add_contact(session, me.id, p.user_id)
        return {"ok": True, "request_id": r.id, "text": "So'rov sardorga yuborildi"}
    if p.kind == "player":  # o'yinchi jamoa qidirmoqda → sardor taklif yuboradi
        r = await invite(session, me.id, p.user_id, out)
        return {"ok": True, "request_id": r.id, "text": "Taklif yuborildi"}
    if p.kind == "scrim":
        mine = await _team_of(session, me.id)
        if mine is None or mine.captain_id != me.id:
            raise BadState("5v5 bahsni jamoa sardori qabul qiladi")
        if mine.id == p.team_id:
            raise BadState("Bu o'z jamoangiz")
        out.user(p.user_id, f"⚔️ 5v5 bahs: «{mine.name}» [{mine.tag}] jamoasi chaqiruvingizni qabul qildi!\nSardor: {who}"
                 + (f"\nYozish: https://t.me/{me.username}" if me.username else ""), webapp_button("Arena", "/arena"))
    else:  # duo, duel
        title = "1v1 duel chaqiruvini qabul qildi" if p.kind == "duel" else "siz bilan rankedda o'ynamoqchi"
        out.user(p.user_id, f"🤝 {who} {title}" + (f" ({extra})" if extra else "")
                 + (f"\nYozish: https://t.me/{me.username}" if me.username else "\nUsername yo'q — botda javob kutadi."),
                 webapp_button("Arena", "/arena"))
    await add_contact(session, me.id, p.user_id)
    owner = await session.get(User, p.user_id)
    return {"ok": True, "username": owner.username if owner and owner.username else None, "text": "Xabar yuborildi"}
