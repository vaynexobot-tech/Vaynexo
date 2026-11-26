from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update

from app.db import SessionLocal
from app.models import DonateOrder, LedgerEntry, PlusSub, ProSlot, Saving, Tournament
from app.services import donate, plus, pro, savings
from app.services.notify import Outbox
from tests.conftest import get_balance, make_package, set_balance

ML = {"player_id": "123456789", "zone_id": "1234"}


def _now():
    return datetime.now(timezone.utc)


async def _complete(order_id: int):
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        o = await s.get(DonateOrder, order_id)
        await donate._finish_success(s, o, "ref", out)


# ---------------------------------------------------------------- signal
async def test_signal_subscribe_and_broadcast(api, ctx):
    for u in (30, 31):
        await set_balance(u, 0)
    assert (await api(30).put("/signals/double", {"on": True})).json() == {"double": True}
    assert (await api(30).get("/signals")).json()["double"] is True
    assert (await api(31).put("/admin/signals/double", {"on": True})).status_code in (403, 405)
    await set_balance(1, 0)
    r = await api(1).post("/admin/signals/double", {"text": ""})
    assert r.json()["sent"] == 1
    assert any(uid == 30 and "Ikki barobar" in t for uid, t, _ in ctx["sent"])
    assert (await api(30).put("/signals/nope", {"on": True})).status_code == 400


async def test_signal_detect_notifies_admin_once():
    from app.models import DonatePackage
    from app.services import signals

    async with SessionLocal() as s, s.begin():
        s.add(DonatePackage(game="ML", name="Double Diamonds 50+50", diamonds=50, bonus=50, price=9000, provider_sku="d50"))
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        assert len(await signals.detect(s, out)) == 1
    async with SessionLocal() as s, s.begin():
        assert await signals.detect(s, out) == []
    assert len(out.items) == 1


# ---------------------------------------------------------------- Plus
async def test_plus_buy_cashback_and_auto(api, ctx):
    await set_balance(40, 200_000)
    r = await api(40).post("/plus/buy")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["active"] and j["days_left"] >= 29 and await get_balance(40) == 200_000 - j["price"]
    bal = await get_balance(40)
    pid = await make_package(37_000)
    r = await api(40).post("/donate/orders", {"package_id": pid, **ML})
    oid = r.json()["id"]
    await _complete(oid)
    assert await get_balance(40) == bal - 37_000 + 37_000 * 3 // 100
    await _complete(oid)  # takror — ikki marta keshbek yo'q
    assert await get_balance(40) == bal - 37_000 + 1_110
    # haftalik avto-xarid
    r = await api(40).put("/plus", {"package_id": pid, **ML})
    assert r.json()["auto"]["title"] == "172 almaz"
    out = Outbox()
    orders = await plus.tick(SessionLocal, out)
    assert len(orders) == 1
    assert await plus.tick(SessionLocal, out) == []  # keyingisi 7 kundan keyin
    # Plus turnir
    async with SessionLocal() as s, s.begin():
        t = Tournament(title="Plus cup", game="ML", prize_fund=1, max_players=10, starts_at=_now() + timedelta(days=1), plus_only=True)
        s.add(t)
    await set_balance(41, 0)
    r = await api(41).post(f"/tournaments/{t.id}/join", {"nick": "a", "game_id": "123456", "server": "1"})
    assert r.status_code == 409 and "Plus" in r.json()["message"]


async def test_plus_auto_renew_and_expire():
    await set_balance(42, 100_000)
    async with SessionLocal() as s, s.begin():
        await plus.buy(s, 42)
    async with SessionLocal() as s, s.begin():
        await s.execute(update(PlusSub).where(PlusSub.user_id == 42).values(until=_now() + timedelta(hours=1)))
    out = Outbox()
    await plus.tick(SessionLocal, out)
    async with SessionLocal() as s:
        sub = await s.get(PlusSub, 42)
        assert sub.months == 2 and sub.until > _now() + timedelta(days=29)
    # pul yetmasa — ogohlantirish, keyin tugaydi
    await set_balance(42, 0)
    async with SessionLocal() as s, s.begin():
        await s.execute(update(PlusSub).where(PlusSub.user_id == 42).values(until=_now() - timedelta(minutes=1)))
    out = Outbox()
    await plus.tick(SessionLocal, out)
    texts = [t for _, t, _ in out.items]
    assert any("yetmayapti" in t for t in texts) and any("tugadi" in t for t in texts)
    out = Outbox()
    await plus.tick(SessionLocal, out)
    assert out.items == []  # qayta-qayta yozmaydi


# ---------------------------------------------------------------- jamg'arma
async def test_savings_flow_bonus_rules(api, ctx):
    await set_balance(50, 100_000)
    pid = await make_package(40_000)
    r = await api(50).post("/savings", {"package_id": pid, **ML, "weekly": 10_000, "first": 15_000})
    assert r.status_code == 200, r.text
    it = r.json()["items"][0]
    assert it["saved"] == 15_000 and it["target"] == 40_000 and await get_balance(50) == 85_000
    sid = it["id"]
    assert (await api(50).post(f"/savings/{sid}/buy")).status_code == 409  # hali yetmagan
    r = await api(50).post(f"/savings/{sid}/deposit", {"amount": 100_000})  # ortig'i olinmaydi
    assert r.json()["items"][0]["saved"] == 40_000 and await get_balance(50) == 60_000
    assert r.json()["items"][0]["bonus_ready"] is False
    # bonus: yarmi 14 kun oldin yig'ilgan bo'lsa
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Saving).where(Saving.id == sid).values(half_at=_now() - timedelta(days=15)))
    r = await api(50).post(f"/savings/{sid}/buy")
    assert r.status_code == 200, r.text
    assert await get_balance(50) == 60_000 + 40_000 * 3 // 100
    assert ("fulfil_donate", r.json()["order_id"], "create") in ctx["jobs"]
    async with SessionLocal() as s:
        sv = await s.get(Saving, sid)
        assert sv.status == "done" and sv.bonus == 1_200


async def test_savings_cancel_and_weekly_tick(api):
    await set_balance(51, 30_000)
    pid = await make_package(40_000)
    sid = (await api(51).post("/savings", {"package_id": pid, **ML, "weekly": 20_000})).json()["items"][0]["id"]
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Saving).where(Saving.id == sid).values(next_at=_now() - timedelta(minutes=1)))
    out = Outbox()
    await savings.tick(SessionLocal, out)
    assert await get_balance(51) == 10_000
    async with SessionLocal() as s, s.begin():
        await s.execute(update(Saving).where(Saving.id == sid).values(next_at=_now() - timedelta(minutes=1)))
    out = Outbox()
    await savings.tick(SessionLocal, out)  # 10 000 yetmaydi
    assert any("yetarli emas" in t for _, t, _ in out.items)
    r = await api(51).post(f"/savings/{sid}/cancel")
    assert r.json()["items"][0]["status"] == "cancelled" and await get_balance(51) == 30_000


# ---------------------------------------------------------------- efirda donat
async def test_stream_register_donate_widget(api, ctx, client):
    await set_balance(60, 0)
    await set_balance(61, 200_000)
    r = await api(60).post("/stream/me", {"slug": "Aziz_Live", "name": "Aziz Live", "player_id": "987654321", "zone_id": "2001"})
    assert r.status_code == 200, r.text
    st = r.json()["streamer"]
    token = st["widget"].rsplit("/", 1)[1]
    assert st["slug"] == "aziz_live"
    feed = (await client.get(f"/api/stream/feed/{token}?after=-1")).json()
    assert feed == {"last": 0, "items": []}
    assert (await client.get(f"/api/stream/w/{token}")).status_code == 200
    assert (await client.get("/api/stream/w/wrong")).status_code == 404
    pid = await make_package(37_000)
    r = await api(61).post("/stream/s/aziz_live/donate", {"kind": "pack", "package_id": pid, "message": "zo'r! https://spam.uz @spam"})
    assert r.status_code == 200, r.text
    async with SessionLocal() as s:
        o = await s.get(DonateOrder, r.json()["order_id"])
        assert o.player_id == "987654321" and o.zone_id == "2001" and o.user_id == 61
    r = await api(61).post("/stream/s/aziz_live/donate", {"kind": "money", "amount": 10_000, "message": "salom", "anon": True})
    assert r.status_code == 200, r.text
    assert await get_balance(60) == 9_000  # 10% platforma
    assert await get_balance(61) == 200_000 - 37_000 - 10_000
    items = (await client.get(f"/api/stream/feed/{token}?after=0")).json()["items"]
    assert [i["kind"] for i in items] == ["pack", "money"]
    assert items[0]["message"] == "zo'r!" and items[1]["name"] == "Anonim"
    assert (await api(60).post("/stream/s/aziz_live/donate", {"kind": "money", "amount": 10_000})).status_code == 409  # o'ziga
    async with SessionLocal() as s:
        kinds = [e.kind for e in await s.scalars(select(LedgerEntry).where(LedgerEntry.user_id == 60))]
        assert kinds == ["stream_payout"]
    page = (await api(61).get("/stream/s/aziz_live")).json()
    assert page["name"] == "Aziz Live" and page["count"] == 2


# ---------------------------------------------------------------- Pro auksion
async def test_pro_auction_full_flow(api, ctx):
    for u, b in ((70, 0), (71, 100_000), (72, 100_000), (1, 0)):
        await set_balance(u, b)
    r = await api(70).post("/pro/apply", {"name": "ProAziz", "rank": "Mythical Immortal", "link": "https://t.me/x"})
    assert r.json()["profile"]["status"] == "pending"
    slot = {"title": "1 ta ranked o'yin", "play_at": (_now() + timedelta(days=1)).isoformat(),
            "ends_at": (_now() + timedelta(hours=2)).isoformat(), "min_bid": 20_000, "step": 5_000}
    assert (await api(70).post("/pro/slots", slot)).status_code == 403
    assert len((await api(1).get("/admin/pro")).json()["applications"]) == 1
    await api(1).post("/admin/pro/apps/70", {"approve": True})
    r = await api(70).post("/pro/slots", slot)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert (await api(70).post(f"/pro/{sid}/bid", {"amount": 30_000})).status_code == 409  # o'ziga
    assert (await api(71).post(f"/pro/{sid}/bid", {"amount": 10_000})).status_code == 400  # kam
    assert (await api(71).post(f"/pro/{sid}/bid", {"amount": 20_000})).json()["leading"] is True
    assert await get_balance(71) == 80_000
    assert (await api(72).post(f"/pro/{sid}/bid", {"amount": 22_000})).status_code == 400  # qadam 5 000
    r = await api(72).post(f"/pro/{sid}/bid", {"amount": 25_000})
    assert r.json()["price"] == 25_000
    assert await get_balance(71) == 100_000 and await get_balance(72) == 75_000
    assert any(uid == 71 and "oshib ketishdi" in t for uid, t, _ in ctx["sent"])
    # tugash → g'olib
    async with SessionLocal() as s, s.begin():
        await s.execute(update(ProSlot).where(ProSlot.id == sid).values(ends_at=_now() - timedelta(seconds=1)))
    out = Outbox()
    await pro.tick(SessionLocal, out)
    d = (await api(72).get(f"/pro/{sid}")).json()
    assert d["status"] == "sold" and d["winner"] and d["contact"] == "@dev70" or d["contact"].startswith("U70") or "70" in d["contact"]
    # nizo → admin qaytaradi
    await api(72).post(f"/pro/{sid}/dispute", {"reason": "kelmadi"})
    r = await api(1).post(f"/admin/pro/disputes/{sid}", {"pay": False})
    assert r.status_code == 200 and await get_balance(72) == 100_000 and await get_balance(70) == 0


async def test_pro_confirm_pays_and_antisnipe(api):
    for u, b in ((73, 0), (74, 100_000)):
        await set_balance(u, b)
    await api(73).post("/pro/apply", {"name": "Pro2"})
    async with SessionLocal() as s, s.begin():
        from app.models import ProProfile

        (await s.get(ProProfile, 73)).status = "approved"
    sid = (await api(73).post("/pro/slots", {"title": "Duo", "play_at": (_now() + timedelta(days=1)).isoformat(),
                                             "ends_at": (_now() + timedelta(minutes=30)).isoformat(), "min_bid": 20_000, "step": 1_000})).json()["id"]
    async with SessionLocal() as s, s.begin():
        await s.execute(update(ProSlot).where(ProSlot.id == sid).values(ends_at=_now() + timedelta(seconds=30)))
    await api(74).post(f"/pro/{sid}/bid", {"amount": 50_000})
    async with SessionLocal() as s:
        assert (await s.get(ProSlot, sid)).ends_at > _now() + timedelta(seconds=100)  # anti-snipe
    async with SessionLocal() as s, s.begin():
        await s.execute(update(ProSlot).where(ProSlot.id == sid).values(ends_at=_now() - timedelta(seconds=1)))
    await pro.tick(SessionLocal, Outbox())
    r = await api(74).post(f"/pro/{sid}/confirm")
    assert r.json()["status"] == "done"
    assert await get_balance(73) == 42_500  # 15% platforma
    assert (await api(74).post(f"/pro/{sid}/confirm")).status_code == 409
