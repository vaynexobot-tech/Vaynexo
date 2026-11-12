from app.services import channel
from tests.test_flows import LISTING


class FakeTg:
    def __init__(self):
        self.posts, self.edits, self.deleted, self.n = [], [], [], 100

    async def post(self, chat, photo, text, kb):
        self.n += 1
        self.posts.append((chat, photo, text, kb))
        return self.n, "p" if photo else "t"

    async def edit(self, chat, msg_id, kind, text, kb):
        self.edits.append((msg_id, kind, text, kb))

    async def delete(self, chat, msg_id):
        self.deleted.append(msg_id)


async def test_listing_channel_sync(api, monkeypatch):
    from app.config import settings

    fake = FakeTg()
    monkeypatch.setattr(channel, "tg", fake)
    monkeypatch.setattr(settings, "bot_username", "VaynexoBot")
    lid = (await api(40).post("/listings", {**LISTING, "media": [{"type": "image", "url": "/media/a.jpg"}]})).json()["id"]
    assert await channel.sync_batch() == 0  # kanal ulanmagan
    await channel.set_channel(-100500)
    assert await channel.sync_batch() == 0  # moderatsiyada — chiqmaydi
    await api(1).post(f"/admin/listings/{lid}/moderate", {"approve": True})
    assert await channel.sync_batch() == 1
    chat, photo, text, kb = fake.posts[0]
    assert chat == -100500 and photo.endswith("/media/a.jpg") and "420 000 so'm" in text
    assert kb["inline_keyboard"][0][0]["url"] == f"https://t.me/VaynexoBot?startapp=listing_{lid}"
    assert await channel.sync_batch() == 0  # o'zgarmagan — qayta yuborilmaydi
    # narx o'zgardi → qayta moderatsiya → post o'chadi, tasdiqlangach yangisi chiqadi
    await api(40).put(f"/listings/{lid}", {**LISTING, "price": 400_000})
    assert await channel.sync_batch() == 1 and fake.deleted == [101]
    await api(1).post(f"/admin/listings/{lid}/moderate", {"approve": True})
    await channel.sync_batch()
    assert "400 000 so'm" in fake.posts[-1][2]
    # sotib olindi → BAND (tugmasiz)
    from tests.conftest import set_balance

    await set_balance(41, 1_000_000)
    r = await api(41).post(f"/listings/{lid}/buy")
    assert r.status_code == 200, r.text
    assert await channel.sync_batch() == 1
    msg_id, kind, text, kb = fake.edits[-1]
    assert "BAND" in text and kb is None
