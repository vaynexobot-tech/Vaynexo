from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.config import settings

_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def enqueue(job: str, *args, **kwargs) -> None:
    pool = await get_pool()
    await pool.enqueue_job(job, *args, **kwargs)
