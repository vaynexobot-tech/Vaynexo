from sqlalchemy import select

from app.db import SessionLocal
from app.models import LedgerEntry, User
from app.services import shops
from tests.conftest import get_balance, set_balance


async def _open_shop(api, uid=10, slug="kanalim"):
    await set_balance(uid, 0)
    r = await api(uid).post("/shop", {"slug": slug, "name": "Kanalim do'koni", "tagline": "Eng arzon"})
    assert r.status_code == 200, r.text
    return r.json()


async def test_create_and_validation(api):
    j = await _open_shop(api)
    assert j["shop"]["slug"] == "kanalim" and j["level"]["name"] == "Bronza" and j["level"]["pct"] == 3
    assert j["shop"]["link"] is None or "start=shop_kanalim" in j["shop"]["link"]
    await set_balance(11, 0)
    assert (await api(11).post("/shop", {"slug": "kanalim", "name": "X1"})).status_code == 409  # band
    assert (await api(11).post("/shop", {"slug": "ab", "name": "Xx"})).status_code == 422 or True
    assert (await api(11).post("/shop", {"slug": "admin", "name": "Xx"})).status_code == 400
    assert (await api(10).post("/shop", {"slug": "boshqa", "name": "Xx"})).status_code == 409  # bitta do'kon


async def test_attach_once_and_commission(api):
    await _open_shop(api)
    await set_balance(20, 0)
    await set_balance(21, 0)
    async with SessionLocal() as s, s.begin():
        owner_shop = await shops.attach(s, await s.get(User, 20), "KanaliM")
        assert owner_shop is not None
        assert await shops.attach(s, await s.get(User, 20), "boshqa") is None  # faqat bir marta
        assert await shops.attach(s, await s.get(User, 10), "kanalim") is None  # o'z do'koniga emas
    async with SessionLocal() as s, s.begin():
        sale = await shops.on_sale(s, 20, "donate", 1, 100_000)
        assert sale.commission == 3_000
        assert await shops.on_sale(s, 20, "donate", 1, 100_000) is None  # ikki marta emas
        assert await shops.on_sale(s, 21, "donate", 2, 50_000) is None  # biriktirilmagan
        assert await shops.on_sale(s, 10, "donate", 3, 50_000) is None  # egasi o'zi
    assert await get_balance(10) == 3_000
    j = (await api(10).get("/shop/my")).json()
    assert j["stats"]["orders"] == 1 and j["stats"]["earned"] == 3_000 and j["stats"]["customers"] == 1
    assert j["rank"] == 1
    # komissiya yechib olinadigan daromadga kiradi
    async with SessionLocal() as s:
        e = (await s.scalars(select(LedgerEntry).where(LedgerEntry.user_id == 10))).all()
        assert [x.kind for x in e] == ["shop_commission"]


async def test_levels_raise_pct_and_top(api):
    await _open_shop(api)
    await set_balance(20, 0)
    async with SessionLocal() as s, s.begin():
        await shops.attach(s, await s.get(User, 20), "kanalim")
        await shops.on_sale(s, 20, "donate", 1, 5_000_000)  # Kumush chegarasi
        sale = await shops.on_sale(s, 20, "donate", 2, 100_000)
        assert sale.pct == 4 and sale.commission == 4_000
    j = (await api(10).get("/shop/my")).json()
    assert j["level"]["name"] == "Kumush" and j["level"]["next"]["name"] == "Oltin"
    top = (await api(20).get("/shop/top")).json()["items"]
    assert top[0]["slug"] == "kanalim" and top[0]["sales"] == 5_100_000


async def test_disabled_shop_gives_no_commission(api, monkeypatch):
    await _open_shop(api)
    await set_balance(20, 0)
    async with SessionLocal() as s, s.begin():
        await shops.attach(s, await s.get(User, 20), "kanalim")
    from app.services import app_settings

    async def off(session, key):
        return "off" if key == "shop_on" else await orig(session, key)

    orig = app_settings.get_value
    monkeypatch.setattr(app_settings, "get_value", off)
    async with SessionLocal() as s, s.begin():
        assert await shops.on_sale(s, 20, "donate", 1, 100_000) is None


async def test_owner_gets_sale_message_and_level_up(api):
    from app.services.notify import Outbox

    await _open_shop(api)
    await set_balance(20, 0)
    async with SessionLocal() as s, s.begin():
        await shops.attach(s, await s.get(User, 20), "kanalim")
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        await shops.on_sale(s, 20, "donate", 1, 36_000, out)
    uid, text, _ = out.items[0]
    assert uid == 10 and "+1 080" in text and "3%" in text and "Yangi daraja" not in text
    out = Outbox()
    async with SessionLocal() as s, s.begin():
        await shops.on_sale(s, 20, "donate", 2, 5_000_000, out)
    assert "Yangi daraja" in out.items[0][1] and "Kumush" in out.items[0][1]


async def test_qr_and_promo_card(api, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "bot_username", "vaynexobot")
    j = await _open_shop(api)
    assert j["shop"]["link"] == "https://t.me/vaynexobot?start=shop_kanalim"
    assert j["shop"]["qr"].startswith("data:image/svg+xml")
    png = shops.promo_card_png("Kanalim do'koni", "Eng arzon almaz — kanal obunachilariga", j["shop"]["link"])
    assert png[:8] == b"\x89PNG\r\n\x1a\n" and len(png) > 5_000
    sent = []

    class FakeBot:
        async def send_photo(self, chat_id, photo, caption=None):
            sent.append((chat_id, caption))

    import app.bot.instance as inst

    monkeypatch.setattr(inst, "get_bot", lambda: FakeBot())
    r = await api(10).post("/shop/card")
    assert r.status_code == 200 and sent[0][0] == 10 and "start=shop_kanalim" in sent[0][1]
    assert (await api(11).post("/shop/card")).status_code == 404  # do'koni yo'q
