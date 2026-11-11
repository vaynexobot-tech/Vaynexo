import os

os.environ.update(
    DATABASE_URL=os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://postgres@/vaynexo_test?host=/tmp"),
    REDIS_URL=os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/15"),
    DB_NULL_POOL="true",
    DEV_MODE="true",
    BOT_TOKEN="123456:TEST",
    ADMIN_IDS="1",
    P2P_SECRET="test-secret",
    ENCRYPTION_KEY="feor9McLug-zG-YkMkh_SM_OeN3yh9fplPQb6eDBkpY=",
    REFERRAL_BONUS="2000",
    COMMISSION_PERCENT="5",
    MEDIA_DIR="/tmp/vaynexo-test-media",
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app import models  # noqa: E402,F401
from app.api import admin as admin_api  # noqa: E402
from app.api import deps  # noqa: E402
from app.api import donate as donate_api  # noqa: E402
from app.api import services as services_api  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.models import DonatePackage, User  # noqa: E402
from app.services import notify  # noqa: E402

_schema_ready = False


@pytest.fixture(autouse=True)
async def db():
    global _schema_ready
    async with engine.begin() as conn:
        if not _schema_ready:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
            _schema_ready = True
        tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
        await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture(autouse=True)
async def isolate(monkeypatch):
    # Testlarda KYC majburiy emas (alohida testda yoqiladi), garant komissiyasi 5%
    from dataclasses import replace as _replace

    from app.services import app_settings as _A

    for _k, _v in (("kyc_marketplace", "off"), ("kyc_rental", "off"), ("garant_fee_percent", 5)):
        monkeypatch.setitem(_A.SCHEMA, _k, _replace(_A.SCHEMA[_k], default=_v))
    deps._redis = None
    try:
        await deps.get_redis().flushdb()
    except Exception:
        pass
    sent: list[tuple[int, str, dict | None]] = []

    async def fake_send(chat_id, text_, markup):
        sent.append((chat_id, text_, markup))

    notify.set_sender(fake_send)
    jobs: list[tuple] = []

    async def fake_enqueue(job, *args, **kw):
        jobs.append((job, *args))

    for mod in (donate_api, services_api, admin_api):
        monkeypatch.setattr(mod, "enqueue", fake_enqueue)
    yield {"sent": sent, "jobs": jobs}
    await deps.get_redis().aclose()
    deps._redis = None


@pytest.fixture
def ctx(isolate):
    return isolate


@pytest.fixture
async def client():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=fastapi_app), base_url="http://test") as c:
        yield c


class Api:
    """Berilgan foydalanuvchi nomidan so'rov yuborish."""

    def __init__(self, client: httpx.AsyncClient, uid: int):
        self.c, self.uid = client, uid

    def _h(self):
        return {"X-Dev-User": str(self.uid)}

    async def get(self, url, **kw):
        return await self.c.get("/api" + url, headers=self._h(), **kw)

    async def post(self, url, json=None, **kw):
        return await self.c.post("/api" + url, json=json or {}, headers=self._h(), **kw)

    async def put(self, url, json=None):
        return await self.c.put("/api" + url, json=json or {}, headers=self._h())

    async def patch(self, url, json=None):
        return await self.c.patch("/api" + url, json=json or {}, headers=self._h())


@pytest.fixture
def api(client):
    return lambda uid: Api(client, uid)


async def set_balance(uid: int, amount: int):
    async with SessionLocal() as s, s.begin():
        u = await s.get(User, uid)
        if u is None:
            s.add(User(id=uid, first_name=f"U{uid}", balance=amount, is_admin=uid == 1))
        else:
            u.balance = amount


async def get_balance(uid: int) -> int:
    async with SessionLocal() as s:
        return (await s.get(User, uid)).balance


async def make_package(price=37_000, game="ML") -> int:
    async with SessionLocal() as s, s.begin():
        p = DonatePackage(game=game, name="172 almaz", diamonds=156, bonus=16, price=price, provider_sku="ML_172")
        s.add(p)
    return p.id
