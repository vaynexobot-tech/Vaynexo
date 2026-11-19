"""Turnir setkasi (olimpiya tizimi) va jamoaviy turnirlar."""

import math
import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import BadState, NotFound
from app.models import Team, TeamMember, Tournament, TournamentEntry, TournamentMatch
from app.services import app_settings, arena
from app.services.notify import Outbox, webapp_button

TEAM_MIN = 5  # jamoaviy turnirga kamida 5 kishi


async def team_for_entry(session: AsyncSession, captain_id: int) -> tuple[Team, list[TeamMember]]:
    tid = await session.scalar(select(TeamMember.team_id).where(TeamMember.user_id == captain_id))
    team = await session.get(Team, tid) if tid else None
    if team is None or team.status != "active":
        raise BadState("Jamoaviy turnir uchun avval jamoa tuzing (Arena → Qidiruv → Jamoa)")
    if team.captain_id != captain_id:
        raise BadState("Jamoani faqat sardor ro'yxatdan o'tkazadi")
    members = list(await session.scalars(select(TeamMember).where(TeamMember.team_id == team.id)))
    if len(members) < TEAM_MIN:
        raise BadState(f"Jamoada kamida {TEAM_MIN} kishi bo'lishi kerak (hozir {len(members)})")
    return team, members


async def _members_of_entry(session: AsyncSession, e: TournamentEntry) -> list[int]:
    if e.team_id:
        return list(await session.scalars(select(TeamMember.user_id).where(TeamMember.team_id == e.team_id)))
    return [e.user_id]


async def generate(session: AsyncSession, t_id: int, out: Outbox) -> None:
    t = await session.get(Tournament, t_id, with_for_update=True)
    if t is None:
        raise NotFound("Turnir")
    if await session.scalar(select(func.count()).select_from(TournamentMatch).where(TournamentMatch.tournament_id == t_id)):
        raise BadState("Setka allaqachon yaratilgan")
    entries = list(await session.scalars(select(TournamentEntry).where(TournamentEntry.tournament_id == t_id)))
    if len(entries) < 2:
        raise BadState("Setka uchun kamida 2 ishtirokchi kerak")
    random.shuffle(entries)
    size = 2 ** math.ceil(math.log2(len(entries)))
    rounds = int(math.log2(size))
    # Juft bo'lmaganlarga «avtomatik o'tish»: bo'sh joylar har juftning ikkinchi o'rniga taqsimlanadi
    seeds: list[TournamentEntry | None] = [None] * size
    byes = size - len(entries)
    it = iter(entries)
    for i in range(size // 2):
        seeds[2 * i] = next(it)
        seeds[2 * i + 1] = None if i < byes else next(it)
    matches: dict[tuple[int, int], TournamentMatch] = {}
    for r in range(1, rounds + 1):
        for s in range(size // (2 ** r)):
            m = TournamentMatch(tournament_id=t_id, round=r, slot=s)
            session.add(m)
            matches[(r, s)] = m
    for s in range(size // 2):
        a, b = seeds[2 * s], seeds[2 * s + 1]
        m = matches[(1, s)]
        m.a_entry_id, m.b_entry_id = (a.id if a else None), (b.id if b else None)
    await session.flush()
    for s in range(size // 2):  # avtomatik o'tganlar keyingi raundga
        m = matches[(1, s)]
        if m.a_entry_id and not m.b_entry_id:
            await _advance(session, t, m, m.a_entry_id, out, notify=False)
    t.status = "running"
    for e in entries:
        for uid in await _members_of_entry(session, e):
            out.user(uid, f"🏆 «{t.title}» setkasi tayyor! Raqibingizni ko'ring.", webapp_button("Setka", f"/arena/{t_id}"))


async def _advance(session: AsyncSession, t: Tournament, m: TournamentMatch, entry_id: int, out: Outbox, notify: bool = True) -> None:
    m.winner_entry_id = entry_id
    nxt = await session.scalar(select(TournamentMatch).where(TournamentMatch.tournament_id == t.id, TournamentMatch.round == m.round + 1,
                                                             TournamentMatch.slot == m.slot // 2))
    if nxt is None:  # final
        await _finish(session, t, entry_id, out)
        return
    if m.slot % 2 == 0:
        nxt.a_entry_id = entry_id
    else:
        nxt.b_entry_id = entry_id
    if notify:
        e = await session.get(TournamentEntry, entry_id)
        for uid in await _members_of_entry(session, e):
            out.user(uid, f"✅ «{t.title}»: keyingi bosqichga o'tdingiz!", webapp_button("Setka", f"/arena/{t.id}"))


async def _finish(session: AsyncSession, t: Tournament, entry_id: int, out: Outbox) -> None:
    t.status = "finished"
    e = await session.get(TournamentEntry, entry_id)
    pts = int(await app_settings.get_value(session, "pts_tournament_win"))
    for uid in await _members_of_entry(session, e):
        await arena.add_points(session, uid, pts, "tournament_win", f"tour_win:{t.id}:{uid}")
        out.user(uid, f"🏆 Tabriklaymiz! «{t.title}» turnirida g'alaba qozondingiz. +{pts} ball")
    out.admins(f"🏆 «{t.title}» yakunlandi. G'olib: {e.nick}", topic="boshqa")


async def set_winner(session: AsyncSession, mid: int, entry_id: int, out: Outbox) -> int:
    m = await session.get(TournamentMatch, mid, with_for_update=True)
    if m is None:
        raise NotFound("O'yin")
    if entry_id not in (m.a_entry_id, m.b_entry_id):
        raise BadState("G'olib shu o'yin ishtirokchisi bo'lishi kerak")
    if not (m.a_entry_id and m.b_entry_id):
        raise BadState("Raqib hali aniqlanmagan")
    if m.winner_entry_id:
        raise BadState("Bu o'yin natijasi allaqachon kiritilgan")
    t = await session.get(Tournament, m.tournament_id, with_for_update=True)
    await _advance(session, t, m, entry_id, out)
    return t.id


async def bracket_dict(session: AsyncSession, t_id: int, me: int | None = None) -> dict:
    matches = list(await session.scalars(select(TournamentMatch).where(TournamentMatch.tournament_id == t_id)
                                         .order_by(TournamentMatch.round, TournamentMatch.slot)))
    entries = {e.id: e for e in await session.scalars(select(TournamentEntry).where(TournamentEntry.tournament_id == t_id))}
    my_entries: set[int] = set()
    if me is not None:
        my_team = await session.scalar(select(TeamMember.team_id).where(TeamMember.user_id == me))
        my_entries = {e.id for e in entries.values() if e.user_id == me or (my_team and e.team_id == my_team)}

    def side(eid: int | None) -> dict | None:
        e = entries.get(eid) if eid else None
        return {"entry_id": e.id, "name": e.nick, "mine": e.id in my_entries} if e else None

    rounds: dict[int, list] = {}
    for m in matches:
        rounds.setdefault(m.round, []).append({"id": m.id, "slot": m.slot, "a": side(m.a_entry_id), "b": side(m.b_entry_id),
                                               "winner": m.winner_entry_id})
    n = len(rounds)
    names = {n: "Final", n - 1: "Yarim final", n - 2: "Chorak final"}
    final = rounds.get(n, [{}])[0] if n else {}
    champ = side(final.get("winner")) if final else None
    return {"rounds": [{"round": r, "name": names.get(r, f"{r}-raund"), "matches": ms} for r, ms in sorted(rounds.items())],
            "champion": champ, "entries": len(entries)}
