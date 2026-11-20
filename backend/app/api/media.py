"""Rasm/video yuklash. Rasmlar WebP ga siqiladi (1600px), shunda trafik va disk tejaladi.

Ishlab chiqarishda media katalogini Caddy/Nginx to'g'ridan-to'g'ri beradi (yoki CDN orqasida turadi).
"""

import io
import re
import secrets

from fastapi import APIRouter, Header, Response, UploadFile
from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.orm import undefer
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, SessionDep, rate_limit
from app.config import settings
from app.errors import AppError, NotFound
from app.models import MediaFile

router = APIRouter(tags=["media"])
# Ochiq router (/api prefiksisiz): <img>/<video> teglari sarlavha yubormaydi
public_router = APIRouter(tags=["media"])

IMAGE_MAX = 5 * 1024 * 1024
VIDEO_MAX = 20 * 1024 * 1024  # video ham bazada turadi — hajmi cheklangan
VIDEO_TYPES = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm"}
CTYPES = {".webp": "image/webp", ".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{8,32}\.(webp|mp4|mov|webm)$")


def _process_image(data: bytes) -> bytes:
    try:
        img = Image.open(io.BytesIO(data))
        img = ImageOps.exif_transpose(img)
        img.thumbnail((1600, 1600))
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, "WEBP", quality=82, method=4)
        return buf.getvalue()
    except Exception as e:  # noqa: BLE001 — har qanday buzuq fayl
        raise AppError("bad_image", "Rasmni o'qib bo'lmadi") from e


async def _read_limited(file: UploadFile, limit: int) -> bytes:
    chunks, size = [], 0
    while chunk := await file.read(1024 * 1024):
        size += len(chunk)
        if size > limit:
            raise AppError("too_large", f"Fayl hajmi {limit // (1024 * 1024)} MB dan oshmasin", 413)
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/media")
async def upload(file: UploadFile, user: CurrentUser, session: SessionDep):
    await rate_limit(f"media:{user.id}", limit=20, window=300)
    ctype = (file.content_type or "").lower()
    uid = user.id
    name = secrets.token_urlsafe(12)
    if ctype.startswith("image/"):
        data = await run_in_threadpool(_process_image, await _read_limited(file, IMAGE_MAX))
        fname, kind, ct = name + ".webp", "image", "image/webp"
    elif ctype in VIDEO_TYPES:
        data = await _read_limited(file, VIDEO_MAX)
        fname, kind, ct = name + VIDEO_TYPES[ctype], "video", ctype
    else:
        raise AppError("bad_type", "Faqat rasm yoki video (mp4/mov/webm)")
    async with session.begin():
        session.add(MediaFile(name=fname, user_id=uid, kind=kind, content_type=ct, size=len(data), data=data))
    return {"type": kind, "url": f"{settings.media_url}/db/{fname}"}


@public_router.get(settings.media_url + "/db/{name}")
async def serve(name: str, session: SessionDep, range: str | None = Header(None)):
    """Bazadan beradi. Uzoq keshlanadi (nomi tasodifiy va o'zgarmaydi); video uchun Range qo'llab-quvvatlanadi."""
    if not NAME_RE.match(name):
        raise NotFound("Fayl")
    m = await session.scalar(select(MediaFile).options(undefer(MediaFile.data)).where(MediaFile.name == name))
    if m is None:
        raise NotFound("Fayl")
    data, ct = m.data, m.content_type
    await session.rollback()
    head = {"Cache-Control": "public, max-age=31536000, immutable", "Accept-Ranges": "bytes"}
    r = re.match(r"bytes=(\d*)-(\d*)$", range or "")
    if r and (r.group(1) or r.group(2)):
        total = len(data)
        if r.group(1):
            start = int(r.group(1))
            end = min(int(r.group(2)), total - 1) if r.group(2) else total - 1
        else:  # bytes=-N — oxirgi N bayt
            start, end = max(0, total - int(r.group(2))), total - 1
        if start > end or start >= total:
            return Response(status_code=416, headers={"Content-Range": f"bytes */{total}"})
        return Response(data[start:end + 1], status_code=206, media_type=ct,
                        headers={**head, "Content-Range": f"bytes {start}-{end}/{total}"})
    return Response(data, media_type=ct, headers=head)
