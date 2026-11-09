"""Fon ishlari navbati.

* REDIS_URL berilgan bo'lsa — arq + Redis (alohida `python -m app.worker` jarayoni). Ko'p foydalanuvchi uchun.
* REDIS_URL bo'sh bo'lsa — YENGIL REJIM: ishlar API jarayonining o'zida asyncio vazifalari sifatida bajariladi,
  cron ham shu yerda ishlaydi. Redis'siz kichik hostinglar (alwaysdata va h.k.) uchun.
  Yengil rejimda API faqat BITTA uvicorn worker bilan ishga tushirilishi kerak.
"""

import asyncio
import logging
from datetime import timedelta

from app.config import settings

log = logging.getLogger(__name__)
LITE = not settings.redis_url

_pool = None


def redis_settings():
    from arq.connections import RedisSettings

    return RedisSettings.from_dsn(settings.redis_url)


async def get_pool():
    global _pool
    if _pool is None:
        from arq import create_pool

        _pool = await create_pool(redis_settings())
    return _pool


async def enqueue(job: str, *args, **kwargs) -> None:
    if LITE:
        await _lite.enqueue_job(job, *args, **kwargs)
        return
    pool = await get_pool()
    await pool.enqueue_job(job, *args, **kwargs)


# ------------------------------------------------------------------ yengil rejim
class _LiteQueue:
    """arq'ning `ctx["redis"].enqueue_job` interfeysiga mos, jarayon ichidagi navbat."""

    max_tries = 5

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task] = set()
        self._job_ids: set[str] = set()
        self._sem: asyncio.Semaphore | None = None

    def _spawn(self, coro) -> None:
        task = asyncio.get_running_loop().create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def enqueue_job(self, job: str, *args, _defer_by: timedelta | float | None = None, _job_id: str | None = None, **kw):
        if _job_id:
            if _job_id in self._job_ids:
                return None
            self._job_ids.add(_job_id)
        delay = _defer_by.total_seconds() if isinstance(_defer_by, timedelta) else float(_defer_by or 0)
        self._spawn(self._run(job, args, kw, delay, _job_id))
        return True

    async def _run(self, job: str, args, kw, delay: float, job_id: str | None) -> None:
        from arq import Retry

        from app import worker

        fn = getattr(worker, job)
        if self._sem is None:
            self._sem = asyncio.Semaphore(20)
        try:
            for attempt in range(1, self.max_tries + 1):
                if delay:
                    await asyncio.sleep(delay)
                try:
                    async with self._sem:
                        await fn({"redis": self, "job_try": attempt}, *args, **kw)
                    return
                except Retry as e:
                    d = e.defer_score
                    delay = (d / 1000) if d else 5 * attempt
                except Exception:
                    log.exception("Fon ishi xatosi: %s%s", job, args)
                    return
            log.error("Fon ishi %s marta urinishdan keyin to'xtatildi: %s%s", self.max_tries, job, args)
        finally:
            if job_id:
                self._job_ids.discard(job_id)


_lite = _LiteQueue()


async def lite_cron_loop() -> None:
    """Yengil rejimda cron vazifalari (worker o'rniga)."""
    from app import worker

    ctx = {"redis": _lite}
    tick = 0
    while True:
        await asyncio.sleep(60)
        tick += 1
        jobs = [worker.cron_expire_topups]
        if tick % 5 == 0:
            jobs.append(worker.cron_auto_release)
        if tick % 2 == 0:
            jobs.append(worker.cron_rescue_donates)
        for job in jobs:
            try:
                await job(ctx)
            except Exception:
                log.exception("Cron xatosi: %s", job.__name__)
