import logging
from contextlib import asynccontextmanager
from pathlib import Path

from aiogram import Dispatcher
from aiogram.types import Update
from fastapi import FastAPI, Header, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import account, admin, ai, arena, donate, market, media, rent, services, user, wallet
from app.config import settings
from app.errors import AppError

log = logging.getLogger("vaynexo")
dp: Dispatcher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global dp
    logging.basicConfig(level=logging.INFO)
    from app.queue import LITE, lite_cron_loop

    cron_task = None
    if LITE:
        import asyncio

        log.info("Yengil rejim: fon ishlari va cron API jarayonida (Redis'siz)")
        cron_task = asyncio.create_task(lite_cron_loop())
    import asyncio as _aio

    from app.services import tg_bank

    tg_task = _aio.create_task(tg_bank.run_forever())  # bank botlari (Telegram) — sozlanmagan bo'lsa kutib turadi
    if settings.bot_webhook_url and settings.bot_token:
        from app.bot.handlers import router as bot_router
        from app.bot.instance import get_bot

        dp = Dispatcher()
        dp.include_router(bot_router)
        try:
            await get_bot().set_webhook(
                settings.bot_webhook_url.rstrip("/") + "/tg/webhook",
                secret_token=settings.bot_webhook_secret,
                allowed_updates=dp.resolve_used_update_types(),
            )
            log.info("Bot webhook o'rnatildi")
            from app.release import notify_admins_once

            await notify_admins_once()
        except Exception:  # Telegram vaqtincha javob bermasa ham API ishlayversin
            log.exception("Webhook o'rnatilmadi — tokenni va internetni tekshiring, so'ng saytni qayta ishga tushiring")
    yield
    tg_task.cancel()
    if cron_task:
        cron_task.cancel()


app = FastAPI(title="VAYNEXO API", lifespan=lifespan, docs_url="/api/docs" if settings.dev_mode else None, redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(AppError)
async def app_error(request: Request, exc: AppError):
    return JSONResponse({"error": exc.code, "message": exc.message}, status_code=exc.status)


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(x) for x in first.get("loc", [])[1:])
    return JSONResponse({"error": "validation", "message": f"Ma'lumot noto'g'ri: {field}"}, status_code=422)


for r in (user.router, wallet.router, wallet.p2p_router, donate.router, market.router, media.router, services.router, rent.router, admin.router, account.router, ai.router, arena.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health")
async def health():
    return {"ok": True}


@app.post("/tg/webhook", include_in_schema=False)
async def tg_webhook(request: Request, x_telegram_bot_api_secret_token: str | None = Header(None)):
    if dp is None or x_telegram_bot_api_secret_token != settings.bot_webhook_secret:
        return JSONResponse({"ok": False}, status_code=403)
    from app.bot.instance import get_bot

    update = Update.model_validate(await request.json(), context={"bot": get_bot()})
    await dp.feed_update(get_bot(), update)
    return {"ok": True}


# Dev uchun: media fayllarni API o'zi beradi (prod'da Caddy beradi).
Path(settings.media_dir).mkdir(parents=True, exist_ok=True)
app.mount(settings.media_url, StaticFiles(directory=settings.media_dir), name="media")


# Yengil rejim / bitta server: yig'ilgan frontendni API o'zi beradi (Caddy bo'lmaganda).
if settings.frontend_dir and Path(settings.frontend_dir, "index.html").is_file():
    _dist = Path(settings.frontend_dir).resolve()
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str):
        if path.startswith(("api/", "tg/")):
            return JSONResponse({"error": "not_found"}, status_code=404)
        f = (_dist / path).resolve()
        if path and f.is_file() and _dist in f.parents:
            return FileResponse(f)
        return FileResponse(_dist / "index.html", headers={"Cache-Control": "no-cache"})
