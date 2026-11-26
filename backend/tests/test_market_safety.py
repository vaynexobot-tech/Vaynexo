from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from app.db import SessionLocal
from app.models import Deal, Listing, User
from app.services import market
from app.services.notify import Outbox
from tests.conftest import get_balance, set_balance
from tests.test_flows import LISTING


def _on(monkeypatch, **vals):
    from dataclasses import replace

    from app.services import app_settings as A

    for k, v in vals.items():
        monkeypatch.setitem(A.SCHEMA, k, replace(A.SCHEMA[k], default=v))


def _now():
    return datetime.now(timezone.utc)


async def _deal(api, monkeypatch, hold=7, seller=40, buyer=41, **extra):
    _on(monkeypatch, hold_days_new=hold, hold_days_verified=hold)
    await set_balance(seller, 0)
    await set_balance(buyer, 1_000_000)
    lid = (await api(seller).post("/listings", {**LISTING, **extra})).json()["id"]
    await api(1).post(f"/admin/listings/{lid}/moderate", {"approve": True})
    return (await api(buyer).post(f"/listings/{lid}/buy")).json()


async def test_hold_period_then_release(api, monkeypatch, ctx):
    deal = await _deal(api, monkeypatch)
    did = deal["id"]
    assert deal["deliver_by"]
    await api(40).post(f"/deals/{did}/deliver", {"credentials": "login/parol"})
    r = await api(41).post(f"/deals/{did}/confirm")
    assert r.json()["status"] == "holding" and r.json()["hold_until"]
    assert await get_balance(40) == 0  # pul hali sotuvchida emas
    assert "secret" not in str(r.json()) and (await api(41).get(f"/deals/{did}")).json()["credentials"] == "login/parol"
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        assert await market.auto_release(s, out) == 0  # muddat tugamagan
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Deal).where(Deal.id == did).values(hold_until=_now() - timedelta(minutes=1)))
    async with SessionLocal() as s, s.begin():
        assert await market.auto_release(s, out) == 1
    assert (await api(41).get(f"/deals/{did}")).json()["status"] == "completed"
    assert await get_balance(40) == 420_000 - 21_000  # 5% garant


async def test_dispute_during_hold_refunds_buyer(api, monkeypatch):
    deal = await _deal(api, monkeypatch)
    did = deal["id"]
    await api(40).post(f"/deals/{did}/deliver", {"credentials": "login/parol"})
    await api(41).post(f"/deals/{did}/confirm")
    r = await api(41).post(f"/deals/{did}/dispute", {"reason": "Sotuvchi akkauntni qaytarib oldi"})
    assert r.json()["status"] == "disputed"
    await api(1).post(f"/admin/deals/{did}/resolve", {"winner": "buyer", "note": "tasdiqlandi"})
    assert await get_balance(41) == 1_000_000 and await get_balance(40) == 0


async def test_auto_confirm_goes_to_hold_and_verified_seller_shorter(api, monkeypatch):
    _on(monkeypatch, hold_days_new=7, hold_days_verified=1)
    await set_balance(40, 0)
    await set_balance(41, 1_000_000)
    lid = (await api(40).post("/listings", LISTING)).json()["id"]
    await api(1).post(f"/admin/listings/{lid}/moderate", {"approve": True})
    did = (await api(41).post(f"/listings/{lid}/buy")).json()["id"]
    await api(40).post(f"/deals/{did}/deliver", {"credentials": "login/parol"})
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Deal).where(Deal.id == did).values(auto_release_at=_now() - timedelta(minutes=1)))
        await market.auto_release(s, Outbox())
    d = (await api(41).get(f"/deals/{did}")).json()
    assert d["status"] == "holding"
    left = (datetime.fromisoformat(d["hold_until"]) - _now()).total_seconds() / 86400
    assert 6.5 < left < 7.1  # yangi sotuvchi: 7 kun


async def test_seller_misses_deadline_refund_and_strike(api, monkeypatch, ctx):
    _on(monkeypatch, strikes_block=2)
    deal = await _deal(api, monkeypatch, hold=0)
    did = deal["id"]
    async with SessionLocal() as s, s.begin():  # 2 soat qoldi → eslatma
        await s.execute(update(Deal).where(Deal.id == did).values(deliver_by=_now() + timedelta(hours=2)))
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        await market.deadline_tick(s, out)
    assert any("3 soatdan kam" in t for _, t, _ in out.items)
    out2 = Outbox()
    async with SessionLocal() as s, s.begin():
        await market.deadline_tick(s, out2)
    assert out2.items == []  # takror eslatma yo'q
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Deal).where(Deal.id == did).values(deliver_by=_now() - timedelta(minutes=1)))
    async with SessionLocal() as s, s.begin():
        assert await market.deadline_tick(s, Outbox()) == 1
    assert await get_balance(41) == 1_000_000  # pul qaytdi
    async with SessionLocal() as s:
        assert (await s.get(User, 40)).seller_strikes == 1
        assert (await s.get(Deal, did)).status == "refunded"
        lst = await s.get(Listing, deal["listing"]["id"])
        assert lst.status == "active"  # qayta sotuvga chiqdi
    # ikkinchi marta — endi e'lon qo'sha olmaydi
    await _deal(api, monkeypatch, hold=0)
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Deal).where(Deal.status == "paid").values(deliver_by=_now() - timedelta(minutes=1)))
        await market.deadline_tick(s, Outbox())
    r = await api(40).post("/listings", LISTING)
    assert r.status_code == 403 and "e'lon qo'sha olmaysiz" in r.json()["message"]


async def test_chat_blocks_contacts_but_allows_normal_text(api, monkeypatch):
    _on(monkeypatch, chat_block_contacts="on")
    await set_balance(40, 0)
    await set_balance(41, 0)
    lid = (await api(40).post("/listings", LISTING)).json()["id"]
    await api(1).post(f"/admin/listings/{lid}/moderate", {"approve": True})
    cid = (await api(41).post(f"/listings/{lid}/chat")).json()["id"]
    for bad in ("yozing +998 90 123 45 67", "t.me/azizbek", "mening kartam 8600 1234 5678 9012", "@aziz_gamer ga yozing",
                "whatsapp dan gaplashamiz", "https://example.com", "payme orqali tashlayman"):
        r = await api(41).post(f"/chats/{cid}/messages", {"text": bad})
        assert r.status_code == 400 and r.json()["error"] == "contact_blocked", bad
    for ok in ("Salom, 74 ta skin bormi?", "Narxi 420000 so'mmi?", "Mythic 150 yulduz, 80 qahramon"):
        assert (await api(41).post(f"/chats/{cid}/messages", {"text": ok})).status_code == 200, ok


async def test_listing_needs_photos_and_unique_account(api, monkeypatch):
    _on(monkeypatch, market_min_photos=3, market_account_id="on")
    await set_balance(40, 0)
    await set_balance(42, 0)
    acc = {"game_id": "123456789", "zone_id": "1234"}
    r = await api(40).post("/listings", {**LISTING, **acc})
    assert r.status_code == 400 and r.json()["error"] == "few_photos"
    imgs = [{"type": "image", "url": f"/media/{i}.jpg"} for i in range(3)]
    r = await api(40).post("/listings", {**LISTING, "media": imgs})
    assert r.json()["error"] == "bad_account_id"
    r = await api(40).post("/listings", {**LISTING, **acc, "media": imgs})
    assert r.status_code == 200, r.text
    r = await api(42).post("/listings", {**LISTING, **acc, "media": imgs})
    assert r.status_code == 409 and r.json()["error"] == "dup_account"
    r = await api(42).post("/listings", {**LISTING, "game_id": "987654321", "zone_id": "1234", "media": imgs})
    assert r.status_code == 200
    async with SessionLocal() as s:
        lst = await s.get(Listing, r.json()["id"])
        assert lst.account_key and "987654321" not in lst.account_enc  # shifrlangan


async def test_price_hint(api):
    await set_balance(40, 0)
    for p in (400_000, 420_000, 450_000, 480_000):
        lid = (await api(40).post("/listings", {**LISTING, "price": p})).json()["id"]
        await api(1).post(f"/admin/listings/{lid}/moderate", {"approve": True})
    cheap = (await api(40).post("/listings", {**LISTING, "price": 30_000})).json()["id"]
    await api(1).post(f"/admin/listings/{cheap}/moderate", {"approve": True})
    d = (await api(41).get(f"/listings/{cheap}")).json()
    assert d["price_hint"]["level"] == "low" and d["price_hint"]["median"] >= 400_000
