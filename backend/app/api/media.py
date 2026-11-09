"""Rasm/video yuklash. Rasmlar WebP ga siqiladi (1600px), shunda trafik va disk tejaladi.

Ishlab chiqarishda media katalogini Caddy/Nginx to'g'ridan-to'g'ri beradi (yoki CDN orqasida turadi).
"""

import io
import secrets
from pathlib import Path

from fastapi import APIRouter, UploadFile
from PIL import Image, ImageOps
from starlette.concurrency import run_in_threadpool

from app.api.deps import CurrentUser, rate_limit
from app.config import settings
from app.errors import AppError

router = APIRouter(tags=["media"])

IMAGE_MAX = 5 * 1024 * 1024
VIDEO_MAX = 50 * 1024 * 1024
VIDEO_TYPES = {"video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm"}


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
async def upload(file: UploadFile, user: CurrentUser):
    await rate_limit(f"media:{user.id}", limit=20, window=300)
    ctype = (file.content_type or "").lower()
    sub = Path(str(user.id % 1000))
    folder = Path(settings.media_dir) / sub
    folder.mkdir(parents=True, exist_ok=True)
    name = secrets.token_urlsafe(12)
    if ctype.startswith("image/"):
        data = await run_in_threadpool(_process_image, await _read_limited(file, IMAGE_MAX))
        fname, kind = name + ".webp", "image"
    elif ctype in VIDEO_TYPES:
        data = await _read_limited(file, VIDEO_MAX)
        fname, kind = name + VIDEO_TYPES[ctype], "video"
    else:
        raise AppError("bad_type", "Faqat rasm yoki video (mp4/mov/webm)")
    await run_in_threadpool((folder / fname).write_bytes, data)
    return {"type": kind, "url": f"{settings.media_url}/{sub}/{fname}"}
