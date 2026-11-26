"""Arena → Qidiruv: 5v5 bahs, 1v1 duel, rankedga sherik, jamoa topish, jamoalar, hurmat, sherik signali."""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.models import PartnerSignal, Team, TeamPost, User
from app.services import teams as svc
from app.services.notify import Outbox

router = APIRouter(prefix="/arena", tags=["arena"])


@router.get("/search/meta")
async def meta(user: CurrentUser, session: SessionDep):
    sig = await session.get(PartnerSignal, user.id)
    return {"regions": list(svc.REGIONS), "signal": bool(sig and sig.enabled), "my_rank": user.ml_rank or "",
            "my_region": user.ml_region or "", "team_max": svc.TEAM_MAX}


@router.get("/posts")
async def posts(user: CurrentUser, session: SessionDep, kind: str = "duo", lane: str = "", region: str = "", match: int = 0):
    return await svc.list_posts(session, user, kind, lane, region, bool(match))


class PostIn(BaseModel):
    kind: str = Field(pattern="^(player|team|duo|duel|scrim)$")
    name: str = Field("", max_length=64)
    lane: str = Field("", max_length=16)
    rank: str = Field("", max_length=32)
    online: str = Field("", max_length=32)
    note: str = Field("", max_length=300)
    region: str = Field("", max_length=32)
    heroes: list[int] = Field(default_factory=list, max_length=10)


@router.post("/posts")
async def create_post(body: PostIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"apost:{user.id}", limit=8, window=3600)
    out = Outbox()
    async with session.begin():
        p = await svc.create_post(session, user.id, body.model_dump(), out)
        pid = p.id
    await out.flush()
    me = await session.get(User, user.id)
    return next((x for x in await svc.list_posts(session, me, body.kind) if x["id"] == pid), {"id": pid})


@router.post("/posts/{pid}/respond")
async def respond(pid: int, user: CurrentUser, session: SessionDep):
    await rate_limit(f"aresp:{user.id}", limit=15, window=3600)
    out = Outbox()
    async with session.begin():
        me = await session.get(User, user.id)
        r = await svc.respond(session, me, pid, out)
    await out.flush()
    return r


@router.post("/posts/{pid}/close")
async def close_post(pid: int, user: CurrentUser, session: SessionDep):
    from app.errors import NotFound

    async with session.begin():
        p = await session.get(TeamPost, pid)
        if p is None or (p.user_id != user.id and not user.is_admin):
            raise NotFound("E'lon")
        p.status = "closed"
    return {"ok": True}


# ---------------------------------------------------------------- jamoalar
@router.get("/teams")
async def teams(user: CurrentUser, session: SessionDep, q: str = "", open: int = 0):
    return await svc.list_teams(session, q, bool(open))


@router.get("/teams/my")
async def my_team(user: CurrentUser, session: SessionDep):
    return await svc.my_team(session, user.id)


class TeamIn(BaseModel):
    name: str = Field(max_length=40)
    tag: str = Field("", max_length=10)
    region: str = Field("", max_length=32)
    about: str = Field("", max_length=200)
    is_open: bool = True


@router.post("/teams")
async def create_team(body: TeamIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"ateam:{user.id}", limit=5, window=3600)
    async with session.begin():
        await svc.create_team(session, user.id, body.model_dump())
    return await svc.my_team(session, user.id)


class TeamEditIn(BaseModel):
    region: str | None = Field(None, max_length=32)
    about: str | None = Field(None, max_length=200)
    is_open: bool | None = None


@router.patch("/teams/my")
async def edit_team(body: TeamEditIn, user: CurrentUser, session: SessionDep):
    async with session.begin():
        await svc.update_team(session, user.id, body.model_dump(exclude_none=True))
    return await svc.my_team(session, user.id)


@router.get("/teams/{tid}")
async def team(tid: int, user: CurrentUser, session: SessionDep):
    from app.errors import NotFound

    t = await session.get(Team, tid)
    if t is None or t.status != "active":
        raise NotFound("Jamoa")
    return await svc.team_dict(session, t, full=True, me=user.id)


@router.post("/teams/{tid}/join")
async def join(tid: int, user: CurrentUser, session: SessionDep):
    await rate_limit(f"ajoin:{user.id}", limit=10, window=3600)
    out = Outbox()
    async with session.begin():
        await svc.request_join(session, user.id, tid, out)
    await out.flush()
    return {"ok": True}


class InviteIn(BaseModel):
    user_id: int


@router.post("/teams/invite")
async def invite(body: InviteIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await svc.invite(session, user.id, body.user_id, out)
    await out.flush()
    return {"ok": True}


class AnswerIn(BaseModel):
    accept: bool


@router.post("/requests/{rid}")
async def answer(rid: int, body: AnswerIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await svc.answer_request(session, user.id, rid, body.accept, out)
    await out.flush()
    return await svc.my_team(session, user.id)


@router.post("/teams/leave")
async def leave(user: CurrentUser, session: SessionDep):
    async with session.begin():
        await svc.leave(session, user.id)
    return await svc.my_team(session, user.id)


class KickIn(BaseModel):
    user_id: int


@router.post("/teams/kick")
async def kick(body: KickIn, user: CurrentUser, session: SessionDep):
    out = Outbox()
    async with session.begin():
        await svc.kick(session, user.id, body.user_id, out)
    await out.flush()
    return await svc.my_team(session, user.id)


# ---------------------------------------------------------------- hurmat va signal
@router.get("/contacts")
async def contacts(user: CurrentUser, session: SessionDep):
    return await svc.my_contacts(session, user.id)


class RateIn(BaseModel):
    good: bool


@router.post("/rate/{target}")
async def rate(target: int, body: RateIn, user: CurrentUser, session: SessionDep):
    await rate_limit(f"arate:{user.id}", limit=30, window=3600)
    async with session.begin():
        return await svc.rate(session, user.id, target, body.good)


class SignalIn(BaseModel):
    enabled: bool


@router.post("/signal")
async def signal(body: SignalIn, user: CurrentUser, session: SessionDep):
    from app.errors import BadState

    async with session.begin():
        u = await session.get(User, user.id)
        if body.enabled and not u.ml_rank:
            raise BadState("Avval MLBB kartangizda rankingizni kiriting")
        s = await session.get(PartnerSignal, user.id)
        if s is None:
            session.add(PartnerSignal(user_id=user.id, enabled=body.enabled))
        else:
            s.enabled = body.enabled
    return {"signal": body.enabled}
