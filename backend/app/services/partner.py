"""Hamkor dasturi: foydalanuvchi VAYNEXO haqida video joylaydi, ko'rishlar soniga qarab mukofot oladi."""

import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import AppError, BadState, NotFound
from app.models import PartnerVideo, User
from app.services import app_settings, arena
from app.services.notify import Outbox, webapp_button

PLATFORMS = {
    "tiktok": ("tiktok.com", "vm.tiktok.com", "vt.tiktok.com"),
    "instagram": ("instagram.com",),
    "youtube": ("youtube.com", "youtu.be", "m.youtube.com"),
}
TIER_REWARDS = {
    1: "VIP e'lon · 3 kun",
    2: "Turnirlarga bepul kirish · 1 oy",
    3: "Olmos paketi",
    4: "«Rasmiy hamkor» nishoni + 1 oy xizmat haqisiz",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_url(url: str) -> tuple[str, str]:
    """(platforma, toza havola). Domen tekshiriladi, kuzatuv parametrlari olib tashlanadi."""
    url = (url or "").strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    try:
        u = urlparse(url)
    except ValueError as e:
        raise AppError("bad_url", "Havola noto'g'ri") from e
    host = (u.hostname or "").lower().removeprefix("www.")
    for name, hosts in PLATFORMS.items():
        if host in hosts or any(host.endswith("." + h) for h in hosts):
            path = u.path.rstrip("/")
            if len(path) < 3:
                raise AppError("bad_url", "Video havolasini to'liq kiriting")
            query = f"?{u.query}" if name == "youtube" and "v=" in u.query else ""
            return name, f"https://{host}{path}{query}"[:300]
    raise AppError("bad_url", "Faqat TikTok, Instagram yoki YouTube havolasi qabul qilinadi")


async def tiers(session: AsyncSession) -> list[dict]:
    s = await app_settings.get_many(session, "partner_min_views", "partner_tier2_views", "partner_tier3_views", "partner_tier4_views")
    views = [s["partner_min_views"], s["partner_tier2_views"], s["partner_tier3_views"], s["partner_tier4_views"]]
    return [{"tier": i + 1, "views": int(v), "reward": TIER_REWARDS[i + 1]} for i, v in enumerate(views)]


async def submit(session: AsyncSession, user_id: int, url: str, out: Outbox) -> PartnerVideo:
    platform, clean = normalize_url(url)
    if await session.scalar(select(PartnerVideo.id).where(PartnerVideo.url == clean)):
        raise BadState("Bu video allaqachon yuborilgan")
    days = int(await app_settings.get_value(session, "partner_interval_days"))
    if days:
        last = await session.scalar(select(func.max(PartnerVideo.created_at)).where(PartnerVideo.user_id == user_id))
        if last and last > _now() - timedelta(days=days):
            nxt = last + timedelta(days=days)
            raise BadState(f"{days} kunda 1 ta video yuborish mumkin. Keyingisi: {nxt:%d.%m %H:%M}")
    v = PartnerVideo(user_id=user_id, platform=platform, url=clean, status="pending")
    session.add(v)
    await session.flush()
    await arena.bump(session, user_id, "partner_video")
    out.admins(f"🎬 Hamkor videosi #{v.id} ({platform}) tekshiruvga keldi:\n{clean}", webapp_button("Ko'rib chiqish", "/admin"))
    return v


async def review(session: AsyncSession, vid: int, approve: bool, views: int, likes: int, note: str | None, out: Outbox) -> PartnerVideo:
    v = await session.get(PartnerVideo, vid, with_for_update=True)
    if v is None:
        raise NotFound("Video")
    if v.status != "pending":
        raise BadState("Video allaqachon ko'rib chiqilgan")
    v.views, v.likes, v.reviewed_at = max(0, views), max(0, likes), _now()
    if approve:
        ratio = int(await app_settings.get_value(session, "partner_min_like_ratio"))
        tier = max((t["tier"] for t in await tiers(session) if v.views >= t["views"]), default=0)
        if tier == 0:
            raise BadState("Ko'rishlar yetarli emas — rad eting")
        if v.views and v.likes * 100 < v.views * ratio:
            raise BadState(f"Layk/ko'rish nisbati {ratio}% dan kam — rad eting")
        v.status, v.tier, v.reward, v.note = "approved", tier, TIER_REWARDS[tier], note
        await _give_reward(session, v, out)
        out.user(v.user_id, f"✅ Hamkor videongiz tasdiqlandi: {v.views:,} ko'rish.\n🎁 Mukofot: {v.reward}".replace(",", " "),
                 webapp_button("Hamkor", "/partner"))
    else:
        v.status, v.note = "rejected", (note or "Talablarga mos emas")
        out.user(v.user_id, f"❌ Hamkor videongiz rad etildi.\nSabab: {v.note}", webapp_button("Hamkor", "/partner"))
    return v


async def _give_reward(session: AsyncSession, v: PartnerVideo, out: Outbox) -> None:
    """Mukofot avtomatik: VIP kunlari, turnir pass, nishon. Olmos paketi — admin qo'lda bajaradi."""
    u = await session.get(User, v.user_id, with_for_update=True)
    if v.tier == 1:
        u.vip_credit_days += 3
    elif v.tier == 2:
        u.tournament_passes += 4  # ~1 oy haftalik turnirlar
    elif v.tier == 3:
        out.admins(f"💎 Hamkor #{v.id}: foydalanuvchi {u.id} ga olmos paketi berilsin (qo'lda).")
    elif v.tier == 4:
        u.badge = "partner"
        out.admins(f"🤝 Hamkor #{v.id}: foydalanuvchi {u.id} «Rasmiy hamkor» bo'ldi. 50k+ — shaxsiy shartnoma uchun bog'laning.")


def video_dict(v: PartnerVideo) -> dict:
    return {"id": v.id, "platform": v.platform, "url": v.url, "status": v.status, "views": v.views, "likes": v.likes,
            "tier": v.tier, "reward": v.reward, "note": v.note, "created_at": v.created_at.isoformat() if v.created_at else None}


async def overview(session: AsyncSession, user_id: int) -> dict:
    vids = list(await session.scalars(select(PartnerVideo).where(PartnerVideo.user_id == user_id).order_by(PartnerVideo.id.desc()).limit(30)))
    t = await tiers(session)
    s = await app_settings.get_many(session, "partner_count_days", "partner_interval_days", "partner_min_like_ratio")
    total = sum(v.views for v in vids if v.status == "approved")
    best = max((v.tier for v in vids if v.status == "approved"), default=0)
    return {"tiers": [{**x, "done": x["tier"] <= best} for x in t], "videos": [video_dict(v) for v in vids],
            "stats": {"sent": len(vids), "views": total, "pending": sum(v.status == "pending" for v in vids),
                      "to_official": max(0, t[-1]["views"] - total)},
            "rules": {"min_views": t[0]["views"], "count_days": s["partner_count_days"], "interval_days": s["partner_interval_days"],
                      "like_ratio": s["partner_min_like_ratio"]}}
