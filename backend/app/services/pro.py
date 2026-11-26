"""Pro bilan o'yna: mashhur o'yinchi/striminer bilan bitta o'yin uchun joy auksionda sotiladi.

Oqim:
1. O'yinchi «Pro» bo'lish uchun ariza beradi → admin tasdiqlaydi.
2. Pro slot ochadi: sarlavha, o'yin vaqti, auksion tugash vaqti, boshlang'ich narx, qadam.
3. Stavka hamyondan BLOKLANADI; kimdir oshirsa oldingi stavka darhol qaytariladi. Oxirgi 2 daqiqada stavka bo'lsa — auksion 2 daqiqaga uzayadi.
4. Auksion tugaydi → g'olib va pro bir-birining kontaktini oladi.
5. G'olib «O'yin bo'ldi» deydi (yoki o'yin vaqtidan 24 soat o'tib, nizo bo'lmasa avtomatik) → pro'ga pul (platforma ulushisiz).
   «Bo'lmadi» bosilsa — nizo, admin hal qiladi (pro'ga to'lash yoki g'olibga qaytarish).
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.errors import AppError, BadState, Forbidden, NotFound
from app.models import ProBid, ProProfile, ProSlot, User
from app.services import app_settings, wallet
from app.services.notify import Outbox, fmt, webapp_button

SNIPE = timedelta(minutes=2)
RELEASE_AFTER = timedelta(hours=24)
MAX_OPEN = 5


def _now() -> datetime:
    return datetime.now(timezone.utc)


def contact(u: User | None) -> str:
    if u is None:
        return "—"
    return f"@{u.username}" if u.username else f"{u.first_name or 'Foydalanuvchi'} (tg://user?id={u.id})"


async def enabled(session: AsyncSession) -> bool:
    return await app_settings.get_value(session, "pro_on") == "on"


# ---------------------------------------------------------------- ariza
async def apply(session: AsyncSession, user_id: int, name: str, bio: str, link: str, rank: str, out: Outbox) -> ProProfile:
    if not await enabled(session):
        raise BadState("Bo'lim hozircha yopiq")
    name = (name or "").strip()[:48]
    if len(name) < 2:
        raise AppError("bad_name", "Nomingizni kiriting")
    p = await session.get(ProProfile, user_id)
    if p is not None and p.status == "approved":
        p.name, p.bio, p.link, p.rank = name, (bio or "").strip()[:300], (link or "").strip()[:200], (rank or "").strip()[:32]
        return p
    if p is None:
        p = ProProfile(user_id=user_id, name=name)
        session.add(p)
    p.name, p.bio, p.link, p.rank, p.status, p.note = name, (bio or "").strip()[:300], (link or "").strip()[:200], (rank or "").strip()[:32], "pending", ""
    out.admins(f"🎮 Yangi Pro ariza: {p.name} ({p.rank})\n{p.link}\n{p.bio}", webapp_button("Ko'rish", "/admin"), topic="boshqa")
    return p


async def review(session: AsyncSession, user_id: int, approve: bool, note: str, out: Outbox) -> ProProfile:
    p = await session.get(ProProfile, user_id)
    if p is None:
        raise NotFound("Ariza")
    p.status, p.note = ("approved" if approve else "rejected"), (note or "")[:200]
    out.user(user_id, "✅ Siz Pro sifatida tasdiqlandingiz! Endi o'yin joylarini auksionga qo'yishingiz mumkin." if approve
             else "❌ Pro arizangiz rad etildi." + (f"\nSabab: {note}" if note else ""), webapp_button("Pro bilan o'yna", "/pro"))
    return p


# ---------------------------------------------------------------- slotlar
async def create_slot(session: AsyncSession, user_id: int, title: str, details: str, play_at: datetime, ends_at: datetime,
                      min_bid: int, step: int, out: Outbox) -> ProSlot:
    if not await enabled(session):
        raise BadState("Bo'lim hozircha yopiq")
    p = await session.get(ProProfile, user_id)
    if p is None or p.status != "approved":
        raise Forbidden("Avval Pro sifatida tasdiqlaning")
    now = _now()
    if ends_at < now + timedelta(minutes=10) or ends_at > now + timedelta(days=7):
        raise AppError("bad_date", "Auksion 10 daqiqadan 7 kungacha davom etishi mumkin")
    if play_at < ends_at:
        raise AppError("bad_date", "O'yin vaqti auksion tugagandan keyin bo'lsin")
    if play_at > now + timedelta(days=14):
        raise AppError("bad_date", "O'yin vaqti 14 kun ichida bo'lsin")
    lo = int(await app_settings.get_value(session, "pro_min_bid"))
    if min_bid < lo:
        raise AppError("bad_amount", f"Boshlang'ich narx kamida {fmt(lo)}")
    if step < 1_000:
        raise AppError("bad_amount", "Qadam kamida 1 000 so'm")
    n = await session.scalar(select(func.count()).select_from(ProSlot).where(ProSlot.pro_id == user_id, ProSlot.status == "open"))
    if (n or 0) >= MAX_OPEN:
        raise BadState(f"Bir vaqtda {MAX_OPEN} tadan ko'p auksion ochib bo'lmaydi")
    title = (title or "").strip()[:120]
    if len(title) < 3:
        raise AppError("bad_title", "Sarlavha yozing")
    s = ProSlot(pro_id=user_id, title=title, details=(details or "").strip()[:500], play_at=play_at, ends_at=ends_at,
                min_bid=min_bid, step=step, price=0, bids=0, status="open")
    session.add(s)
    await session.flush()
    return s


async def _lock_slot(session: AsyncSession, sid: int) -> ProSlot:
    s = await session.scalar(select(ProSlot).where(ProSlot.id == sid).with_for_update().execution_options(populate_existing=True))
    if s is None:
        raise NotFound("Auksion")
    return s


async def _refund_bid(session: AsyncSession, bid: ProBid, status: str) -> None:
    await wallet.credit(session, bid.user_id, bid.amount, "pro_bid_refund", f"probid:{bid.id}:refund", ref_type="pro", ref_id=bid.slot_id)
    bid.status = status


async def place_bid(session: AsyncSession, user_id: int, sid: int, amount: int, out: Outbox) -> ProSlot:
    if not await enabled(session):
        raise BadState("Bo'lim hozircha yopiq")
    s = await _lock_slot(session, sid)
    now = _now()
    if s.status != "open" or s.ends_at <= now:
        raise BadState("Auksion yakunlangan")
    if s.pro_id == user_id:
        raise BadState("O'z auksioningizga stavka qo'yib bo'lmaydi")
    top = await session.get(ProBid, s.top_bid_id) if s.top_bid_id else None
    if top is not None and top.user_id == user_id:
        raise BadState("Eng yuqori stavka sizniki")
    need = s.min_bid if top is None else s.price + s.step
    if amount < need:
        raise AppError("low_bid", f"Stavka kamida {fmt(need)}")
    if amount > 100_000_000:
        raise AppError("bad_amount", "Juda katta summa")
    bid = ProBid(slot_id=s.id, user_id=user_id, amount=amount, status="active")
    session.add(bid)
    await session.flush()
    await wallet.debit(session, user_id, amount, "pro_bid", f"probid:{bid.id}", ref_type="pro", ref_id=s.id)
    if top is not None:
        await _refund_bid(session, top, "outbid")
        out.user(top.user_id, f"⚡️ «{s.title}» auksionida stavkangizdan oshib ketishdi ({fmt(amount)}). {fmt(top.amount)} hamyonga qaytdi.",
                 webapp_button("Qayta stavka", f"/pro/{s.id}"))
    s.price, s.top_bid_id, s.bids = amount, bid.id, (s.bids or 0) + 1
    if s.ends_at - now < SNIPE:
        s.ends_at = now + SNIPE
    return s


async def cancel_slot(session: AsyncSession, user_id: int, sid: int, out: Outbox) -> ProSlot:
    s = await _lock_slot(session, sid)
    if s.pro_id != user_id:
        raise Forbidden()
    if s.status not in ("open", "sold"):
        raise BadState("Bekor qilib bo'lmaydi")
    top = await session.get(ProBid, s.top_bid_id) if s.top_bid_id else None
    if top is not None and top.status in ("active", "won"):
        await _refund_bid(session, top, "refunded")
        out.user(top.user_id, f"↩️ Pro «{s.title}» o'yinini bekor qildi. {fmt(top.amount)} hamyonga qaytdi.")
    s.status, s.finished_at = "cancelled", _now()
    return s


async def _pay_pro(session: AsyncSession, s: ProSlot, out: Outbox) -> int:
    fee = int(await app_settings.get_value(session, "pro_fee"))
    payout = s.price * (100 - fee) // 100
    if payout > 0:
        await wallet.credit(session, s.pro_id, payout, "pro_payout", f"proslot:{s.id}:pay", ref_type="pro", ref_id=s.id)
    s.status, s.finished_at = "done", _now()
    out.user(s.pro_id, f"💰 «{s.title}» uchun {fmt(payout)} hamyoningizga tushdi.", webapp_button("Hamyon", "/wallet"))
    return payout


async def confirm(session: AsyncSession, user_id: int, sid: int, out: Outbox) -> ProSlot:
    s = await _lock_slot(session, sid)
    if s.winner_id != user_id:
        raise Forbidden()
    if s.status != "sold":
        raise BadState("Holat mos emas")
    await _pay_pro(session, s, out)
    return s


async def dispute(session: AsyncSession, user_id: int, sid: int, reason: str, out: Outbox) -> ProSlot:
    s = await _lock_slot(session, sid)
    if s.winner_id != user_id:
        raise Forbidden()
    if s.status != "sold":
        raise BadState("Holat mos emas")
    s.status, s.dispute = "disputed", (reason or "").strip()[:300]
    out.admins(f"⚠️ Pro auksion nizosi #{s.id}: «{s.title}» — {fmt(s.price)}\nSabab: {s.dispute}", webapp_button("Hal qilish", "/admin"), topic="boshqa")
    out.user(s.pro_id, f"⚠️ G'olib «{s.title}» o'yini bo'lmaganini bildirdi. Admin ko'rib chiqadi.")
    return s


async def resolve(session: AsyncSession, sid: int, pay: bool, out: Outbox) -> ProSlot:
    s = await _lock_slot(session, sid)
    if s.status != "disputed":
        raise BadState("Nizo yo'q")
    if pay:
        await _pay_pro(session, s, out)
        out.user(s.winner_id, f"ℹ️ «{s.title}» nizosi: admin pro foydasiga hal qildi.")
    else:
        top = await session.get(ProBid, s.top_bid_id)
        await _refund_bid(session, top, "refunded")
        s.status, s.finished_at = "cancelled", _now()
        out.user(s.winner_id, f"↩️ «{s.title}» nizosi: {fmt(top.amount)} hamyoningizga qaytarildi.")
        out.user(s.pro_id, f"ℹ️ «{s.title}» nizosi: pul g'olibga qaytarildi.")
    return s


async def tick(sessions: async_sessionmaker, out: Outbox) -> None:
    now = _now()
    async with sessions() as session:
        closing = list(await session.scalars(select(ProSlot.id).where(ProSlot.status == "open", ProSlot.ends_at <= now)))
        release = list(await session.scalars(select(ProSlot.id).where(ProSlot.status == "sold", ProSlot.play_at <= now - RELEASE_AFTER)))
    for sid in closing:
        async with sessions() as session:
            async with session.begin():
                s = await _lock_slot(session, sid)
                if s.status != "open" or s.ends_at > now:
                    continue
                top = await session.get(ProBid, s.top_bid_id) if s.top_bid_id else None
                if top is None:
                    s.status, s.finished_at = "expired", now
                    out.user(s.pro_id, f"⌛️ «{s.title}» auksioni stavkasiz yakunlandi.")
                    continue
                top.status, s.status, s.winner_id = "won", "sold", top.user_id
                pro_u, win_u = await session.get(User, s.pro_id), await session.get(User, top.user_id)
                when = f"{s.play_at:%d.%m %H:%M} (UTC)"
                out.user(top.user_id, f"🏆 Siz «{s.title}» auksionida g'olib bo'ldingiz — {fmt(s.price)}!\nO'yin: {when}\nPro bilan bog'laning: {contact(pro_u)}\n\n"
                         "O'yindan keyin «O'yin bo'ldi» tugmasini bosing. Muammo bo'lsa — «Bo'lmadi».", webapp_button("Ochish", f"/pro/{s.id}"))
                out.user(s.pro_id, f"🎉 «{s.title}» sotildi — {fmt(s.price)}.\nO'yin: {when}\nG'olib: {contact(win_u)}", webapp_button("Ochish", f"/pro/{s.id}"))
    for sid in release:
        async with sessions() as session:
            async with session.begin():
                s = await _lock_slot(session, sid)
                if s.status == "sold" and s.play_at <= now - RELEASE_AFTER:
                    await _pay_pro(session, s, out)


# ---------------------------------------------------------------- ko'rinishlar
def _slot(s: ProSlot, p: ProProfile | None, me: int | None = None, top_uid: int | None = None) -> dict:
    return {"id": s.id, "title": s.title, "details": s.details, "play_at": s.play_at.isoformat(), "ends_at": s.ends_at.isoformat(),
            "min_bid": s.min_bid, "step": s.step, "price": s.price, "bids": s.bids, "status": s.status,
            "next_bid": s.min_bid if not s.top_bid_id else s.price + s.step,
            "pro": {"id": s.pro_id, "name": p.name if p else "Pro", "rank": p.rank if p else "", "bio": p.bio if p else "", "link": p.link if p else ""},
            "mine": me == s.pro_id, "winner": me is not None and me == s.winner_id, "leading": me is not None and me == top_uid}


async def list_open(session: AsyncSession, me: int) -> list[dict]:
    rows = list(await session.scalars(select(ProSlot).where(ProSlot.status == "open").order_by(ProSlot.ends_at).limit(50)))
    profs = {p.user_id: p for p in await session.scalars(select(ProProfile).where(ProProfile.user_id.in_({r.pro_id for r in rows})))} if rows else {}
    tops = {b.id: b.user_id for b in await session.scalars(select(ProBid).where(ProBid.id.in_({r.top_bid_id for r in rows if r.top_bid_id})))} if rows else {}
    return [_slot(r, profs.get(r.pro_id), me, tops.get(r.top_bid_id)) for r in rows]


async def detail(session: AsyncSession, sid: int, me: int) -> dict:
    s = await session.get(ProSlot, sid)
    if s is None:
        raise NotFound("Auksion")
    p = await session.get(ProProfile, s.pro_id)
    top = await session.get(ProBid, s.top_bid_id) if s.top_bid_id else None
    d = _slot(s, p, me, top.user_id if top else None)
    hist = await session.scalars(select(ProBid).where(ProBid.slot_id == sid).order_by(ProBid.id.desc()).limit(10))
    d["history"] = [{"amount": b.amount, "at": b.created_at.isoformat() if b.created_at else None, "me": b.user_id == me} for b in hist]
    if s.status in ("sold", "done", "disputed") and me in (s.pro_id, s.winner_id):
        other = await session.get(User, s.winner_id if me == s.pro_id else s.pro_id)
        d["contact"] = contact(other)
    return d


async def my(session: AsyncSession, me: int) -> dict:
    prof = await session.get(ProProfile, me)
    own = list(await session.scalars(select(ProSlot).where(ProSlot.pro_id == me).order_by(ProSlot.id.desc()).limit(30)))
    won = list(await session.scalars(select(ProSlot).where(ProSlot.winner_id == me).order_by(ProSlot.id.desc()).limit(30)))
    earned = int(await session.scalar(select(func.coalesce(func.sum(ProSlot.price), 0)).where(ProSlot.pro_id == me, ProSlot.status == "done")) or 0)
    cfg = await app_settings.get_many(session, "pro_on", "pro_fee", "pro_min_bid")
    return {"enabled": cfg["pro_on"] == "on", "fee": int(cfg["pro_fee"]), "min_bid": int(cfg["pro_min_bid"]),
            "profile": {"name": prof.name, "bio": prof.bio, "link": prof.link, "rank": prof.rank, "status": prof.status, "note": prof.note} if prof else None,
            "own": [_slot(s, prof, me) for s in own], "won": [_slot(s, None, me) for s in won], "earned": earned}


async def admin_lists(session: AsyncSession) -> dict:
    apps = await session.scalars(select(ProProfile).where(ProProfile.status == "pending").order_by(ProProfile.created_at))
    disputes = list(await session.scalars(select(ProSlot).where(ProSlot.status == "disputed").order_by(ProSlot.id)))
    return {"applications": [{"user_id": p.user_id, "name": p.name, "bio": p.bio, "link": p.link, "rank": p.rank} for p in apps],
            "disputes": [{"id": s.id, "title": s.title, "price": s.price, "reason": s.dispute, "pro_id": s.pro_id, "winner_id": s.winner_id} for s in disputes]}
