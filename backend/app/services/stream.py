"""Efirda donat: tomoshabin striminerga almaz paketi yoki pul yuboradi, efirda alert chiqadi.

- Striminer ro'yxatdan o'tadi: havola nomi, MLBB ID. Unga sahifa `t.me/bot?start=stream_<slug>` va OBS vidjeti beriladi.
- Almaz paketi: odatiy donat buyurtmasi, almaz striminerning MLBB akkauntiga yetkaziladi (daromad — paket ustamasi).
- Pul donati: striminer hamyoniga tushadi (yechib olinadi), platforma ulushi admin sozlamasida.
- Vidjet (OBS → Browser Source) faqat maxfiy token bilan ochiladi va yangi donatlarni ko'rsatadi.
"""

import re
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, BadState, NotFound
from app.models import DonatePackage, StreamDonation, Streamer, User
from app.services import app_settings, wallet
from app.services.notify import Outbox, fmt, webapp_button
from app.services.shops import RESERVED, SLUG_RE, clean_slug

URL_RE = re.compile(r"(https?://\S+|www\.\S+|t\.me/\S+|@\w{3,})", re.I)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def clean_message(text: str) -> str:
    text = URL_RE.sub("", (text or "")).replace("\n", " ").strip()
    return re.sub(r"\s{2,}", " ", text)[:150]


async def enabled(session: AsyncSession) -> bool:
    return await app_settings.get_value(session, "stream_on") == "on"


async def register(session: AsyncSession, user_id: int, slug: str, name: str, about: str, player_id: str, zone_id: str) -> Streamer:
    if not await enabled(session):
        raise BadState("Bo'lim hozircha yopiq")
    name = (name or "").strip()[:48]
    if len(name) < 2:
        raise AppError("bad_name", "Nomingizni kiriting")
    player_id, zone_id = (player_id or "").strip(), (zone_id or "").strip()
    if not re.fullmatch(r"\d{5,20}", player_id) or not re.fullmatch(r"\d{1,10}", zone_id):
        raise AppError("bad_id", "MLBB User ID va Zone ID ni to'g'ri kiriting")
    s = await session.scalar(select(Streamer).where(Streamer.user_id == user_id))
    if s is None:
        slug = clean_slug(slug)
        if not SLUG_RE.match(slug) or slug in RESERVED:
            raise AppError("bad_slug", "Havola nomi: 3–24 ta kichik lotin harf, raqam yoki _")
        if await session.scalar(select(Streamer.id).where(Streamer.slug == slug)):
            raise BadState("Bu nom band, boshqasini tanlang")
        s = Streamer(user_id=user_id, slug=slug, widget_token=secrets.token_urlsafe(24), active=True,
                     total_count=0, total_packs=0, total_money=0)
        session.add(s)
    s.name, s.about, s.player_id, s.zone_id = name, (about or "").strip()[:160], player_id, zone_id
    await session.flush()
    return s


async def by_slug(session: AsyncSession, slug: str) -> Streamer:
    s = await session.scalar(select(Streamer).where(Streamer.slug == clean_slug(slug)))
    if s is None or not s.active:
        raise NotFound("Striminer")
    return s


def _donor_name(user: User, anon: bool) -> str:
    if anon:
        return "Anonim"
    return (user.first_name or user.username or "Muxlis")[:48]


async def donate_pack(session: AsyncSession, donor: User, slug: str, package_id: int, message: str, anon: bool, out: Outbox) -> StreamDonation:
    from app.services import donate

    if not await enabled(session):
        raise BadState("Bo'lim hozircha yopiq")
    s = await by_slug(session, slug)
    pkg = await session.get(DonatePackage, package_id)
    if pkg is None or not pkg.is_active or pkg.game != "ML" or pkg.delivery == "voucher":
        raise NotFound("Paket")
    order = await donate.create_order(session, donor.id, pkg.id, s.player_id, s.zone_id)
    d = StreamDonation(streamer_id=s.id, donor_id=donor.id, donor_name=_donor_name(donor, anon), kind="pack", title=pkg.name,
                       amount=pkg.price, payout=0, order_id=order.id, message=clean_message(message), hidden=False)
    session.add(d)
    s.total_count += 1
    s.total_packs += pkg.price
    await session.flush()
    out.user(s.user_id, f"🎁 {d.donor_name} sizga {pkg.name} yubordi!" + (f"\n💬 {d.message}" if d.message else "")
             + "\nAlmaz MLBB akkauntingizga yetkazilmoqda.", webapp_button("Panel", "/streamer"))
    return d


async def donate_money(session: AsyncSession, donor: User, slug: str, amount: int, message: str, anon: bool, out: Outbox) -> StreamDonation:
    if not await enabled(session):
        raise BadState("Bo'lim hozircha yopiq")
    s = await by_slug(session, slug)
    if s.user_id == donor.id:
        raise BadState("O'zingizga pul donati yuborib bo'lmaydi")
    cfg = await app_settings.get_many(session, "stream_fee", "stream_min")
    if amount < int(cfg["stream_min"]) or amount > 10_000_000:
        raise AppError("bad_amount", f"Summa {fmt(int(cfg['stream_min']))} dan 10 000 000 so'mgacha")
    payout = amount * (100 - int(cfg["stream_fee"])) // 100
    d = StreamDonation(streamer_id=s.id, donor_id=donor.id, donor_name=_donor_name(donor, anon), kind="money", title=fmt(amount),
                       amount=amount, payout=payout, message=clean_message(message), hidden=False)
    session.add(d)
    await session.flush()
    await wallet.debit(session, donor.id, amount, "stream_donate", f"stream:{d.id}:in", ref_type="stream", ref_id=d.id)
    if payout > 0:
        await wallet.credit(session, s.user_id, payout, "stream_payout", f"stream:{d.id}:out", ref_type="stream", ref_id=d.id)
    s.total_count += 1
    s.total_money += payout
    out.user(s.user_id, f"💸 {d.donor_name} sizga {fmt(amount)} donat qildi (hamyonga +{fmt(payout)})."
             + (f"\n💬 {d.message}" if d.message else ""), webapp_button("Panel", "/streamer"))
    return d


async def test_alert(session: AsyncSession, user_id: int) -> StreamDonation:
    s = await session.scalar(select(Streamer).where(Streamer.user_id == user_id))
    if s is None:
        raise NotFound("Striminer")
    d = StreamDonation(streamer_id=s.id, donor_id=None, donor_name="VAYNEXO", kind="test", title="86 Diamonds",
                       amount=0, payout=0, message="Bu sinov alerti — vidjet ishlayapti! 🎉", hidden=False)
    session.add(d)
    await session.flush()
    return d


async def hide(session: AsyncSession, user_id: int, did: int) -> None:
    d = await session.get(StreamDonation, did)
    s = await session.scalar(select(Streamer).where(Streamer.user_id == user_id))
    if d is None or s is None or d.streamer_id != s.id:
        raise NotFound("Donat")
    d.hidden = True


def _d(d: StreamDonation, private: bool = False) -> dict:
    out = {"id": d.id, "name": d.donor_name, "kind": d.kind, "title": d.title, "amount": d.amount, "message": d.message,
           "at": d.created_at.isoformat() if d.created_at else None}
    if private:
        out.update(payout=d.payout, hidden=d.hidden)
    return out


async def feed(session: AsyncSession, token: str, after: int) -> dict:
    """Vidjet uchun: token bo'yicha yangi donatlar (oxirgi 10 daqiqa)."""
    s = await session.scalar(select(Streamer).where(Streamer.widget_token == token))
    if s is None:
        raise NotFound("Vidjet")
    q = select(StreamDonation).where(StreamDonation.streamer_id == s.id, StreamDonation.hidden.is_(False))
    if after < 0:  # birinchi ochilishda eskilarini qaytadan ko'rsatmaymiz — faqat oxirgi ID
        last = await session.scalar(select(func.max(StreamDonation.id)).where(StreamDonation.streamer_id == s.id))
        return {"last": int(last or 0), "items": []}
    rows = list(await session.scalars(q.where(StreamDonation.id > after, StreamDonation.created_at >= _now() - timedelta(minutes=10))
                                      .order_by(StreamDonation.id).limit(20)))
    return {"last": rows[-1].id if rows else after, "items": [_d(r) for r in rows]}


async def public_page(session: AsyncSession, slug: str) -> dict:
    s = await by_slug(session, slug)
    since = _now() - timedelta(days=30)
    top = (await session.execute(
        select(StreamDonation.donor_name, func.sum(StreamDonation.amount).label("t"))
        .where(StreamDonation.streamer_id == s.id, StreamDonation.kind != "test", StreamDonation.hidden.is_(False),
               StreamDonation.donor_name != "Anonim", StreamDonation.created_at >= since)
        .group_by(StreamDonation.donor_name).order_by(func.sum(StreamDonation.amount).desc()).limit(5))).all()
    recent = await session.scalars(select(StreamDonation).where(
        StreamDonation.streamer_id == s.id, StreamDonation.kind != "test", StreamDonation.hidden.is_(False))
        .order_by(StreamDonation.id.desc()).limit(10))
    cfg = await app_settings.get_many(session, "stream_min", "stream_on")
    return {"slug": s.slug, "name": s.name, "about": s.about, "count": s.total_count, "enabled": cfg["stream_on"] == "on",
            "min_money": int(cfg["stream_min"]), "top": [{"name": n, "total": int(t)} for n, t in top], "recent": [_d(r) for r in recent]}


async def dashboard(session: AsyncSession, user_id: int, bot_username: str, base_url: str) -> dict:
    cfg = await app_settings.get_many(session, "stream_on", "stream_fee", "stream_min")
    s = await session.scalar(select(Streamer).where(Streamer.user_id == user_id))
    res = {"enabled": cfg["stream_on"] == "on", "fee": int(cfg["stream_fee"]), "min_money": int(cfg["stream_min"]), "streamer": None}
    if s is None:
        return res
    rows = await session.scalars(select(StreamDonation).where(StreamDonation.streamer_id == s.id).order_by(StreamDonation.id.desc()).limit(30))
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    t_money, t_count = (await session.execute(select(func.coalesce(func.sum(StreamDonation.payout), 0), func.count()).where(
        StreamDonation.streamer_id == s.id, StreamDonation.kind != "test", StreamDonation.created_at >= today))).one()
    res["streamer"] = {
        "slug": s.slug, "name": s.name, "about": s.about, "player_id": s.player_id, "zone_id": s.zone_id,
        "link": f"https://t.me/{bot_username}?start=stream_{s.slug}" if bot_username else None,
        "widget": f"{base_url.rstrip('/')}/api/stream/w/{s.widget_token}" if base_url else f"/api/stream/w/{s.widget_token}",
        "total_count": s.total_count, "total_packs": s.total_packs, "total_money": s.total_money,
        "today": {"money": int(t_money), "count": int(t_count)},
        "items": [_d(r, True) for r in rows],
    }
    return res


async def rotate_token(session: AsyncSession, user_id: int) -> None:
    s = await session.scalar(select(Streamer).where(Streamer.user_id == user_id))
    if s is None:
        raise NotFound("Striminer")
    s.widget_token = secrets.token_urlsafe(24)


WIDGET_HTML = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>VAYNEXO alert</title>
<style>
html,body{margin:0;background:transparent;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;overflow:hidden}
#box{position:fixed;left:50%;top:40px;transform:translate(-50%,-30px);opacity:0;transition:all .5s cubic-bezier(.2,.9,.3,1.3);
 min-width:420px;max-width:90vw;padding:22px 28px;border-radius:24px;color:#fff;text-align:center;
 background:linear-gradient(135deg,rgba(20,22,40,.92),rgba(40,30,80,.92));border:2px solid #ffd60a;box-shadow:0 10px 40px rgba(255,214,10,.35)}
#box.show{opacity:1;transform:translate(-50%,0)}
.ic{font-size:64px;line-height:1;animation:pop 1s ease infinite alternate}
@keyframes pop{from{transform:scale(1)}to{transform:scale(1.12)}}
.n{font-size:28px;font-weight:800;margin-top:6px}.n b{color:#ffd60a}
.t{font-size:22px;font-weight:700;color:#1de9b6;margin-top:4px}
.m{font-size:20px;margin-top:10px;color:#e6e8f0}
.brand{font-size:11px;letter-spacing:.2em;color:#8a90a8;margin-top:10px}
</style></head><body><div id="box"><div class="ic" id="ic">💎</div><div class="n" id="n"></div><div class="t" id="t"></div>
<div class="m" id="m"></div><div class="brand">VAYNEXO</div></div>
<script>
const F=location.pathname.replace('/w/','/feed/');let last=-1,q=[],busy=false;
function beep(){try{const c=new AudioContext(),o=c.createOscillator(),g=c.createGain();o.connect(g);g.connect(c.destination);
o.type='triangle';o.frequency.setValueAtTime(660,c.currentTime);o.frequency.setValueAtTime(990,c.currentTime+.12);
g.gain.setValueAtTime(.15,c.currentTime);g.gain.exponentialRampToValueAtTime(.001,c.currentTime+.6);o.start();o.stop(c.currentTime+.6)}catch(e){}}
function esc(s){return String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function next(){if(busy||!q.length)return;busy=true;const d=q.shift(),b=document.getElementById('box');
document.getElementById('ic').textContent=d.kind==='money'?'💸':'💎';
document.getElementById('n').innerHTML='<b>'+esc(d.name)+'</b> donat qildi!';
document.getElementById('t').textContent=d.title;document.getElementById('m').textContent=d.message||'';
b.classList.add('show');beep();setTimeout(()=>{b.classList.remove('show');setTimeout(()=>{busy=false;next()},700)},7000)}
async function poll(){try{const r=await fetch(F+'?after='+last);if(r.ok){const j=await r.json();if(last>=0)q.push(...j.items);last=(j.last!==undefined?j.last:last);next()}}catch(e){}
setTimeout(poll,3000)}
poll();
</script></body></html>"""
