from app.db import SessionLocal
from app.models import DonateGame, DonatePackage
from app.services.inline_search import parse_query, search


async def _seed():
    async with SessionLocal() as s, s.begin():
        s.add(DonateGame(slug="pubg-mobile", name="PUBG Mobile", sort=2, fields=[]))
        s.add(DonateGame(slug="hidden", name="Hidden Game", sort=3, fields=[], is_active=False))
        s.add_all([
            DonatePackage(game="ML", name="86 Diamonds (78 + 8)", diamonds=78, bonus=8, price=18100, provider_sku="a", sort=1),
            DonatePackage(game="ML", name="172 Diamonds (156 + 16)", diamonds=156, bonus=16, price=36000, provider_sku="b", sort=2),
            DonatePackage(game="ML", name="1412 Diamonds", diamonds=1412, price=287400, provider_sku="c", sort=3),
            DonatePackage(game="ML", name="Off", diamonds=5, price=100, provider_sku="d", is_active=False),
            DonatePackage(game="pubg-mobile", name="660 UC", diamonds=660, price=124700, provider_sku="e", sort=1),
            DonatePackage(game="hidden", name="86 Coins", diamonds=86, price=1, provider_sku="f"),
        ])


def test_parse_query():
    assert parse_query("ML 86 almaz") == (["ml"], [86])
    assert parse_query("1 412 olmos") == ([], [1412])
    assert parse_query("") == ([], [])


async def test_search_by_number_and_game():
    await _seed()
    async with SessionLocal() as s:
        r = await search(s, "86")
        assert [x["name"] for x in r] == ["86 Diamonds (78 + 8)"]  # yashirin o'yin chiqmaydi
        assert [x["name"] for x in await search(s, "pubg 660")] == ["660 UC"]
        assert [x["name"] for x in await search(s, "uc")] == ["660 UC"]
        assert [x["name"] for x in await search(s, "ml 1 412")] == ["1412 Diamonds"]
        assert len(await search(s, "mlbb")) == 3  # o'chirilgan paket chiqmaydi
        assert await search(s, "noma'lum o'yin") == []
        allr = await search(s, "")
        assert {x["game"] for x in allr} == {"ML", "pubg-mobile"} and allr[0]["game"] == "ML"


def test_deep_link_donate():
    from app.bot.handlers import deep_link_path

    assert deep_link_path("donate_ML") == ("/donate/ML", "💎 Donat qilish")
    assert deep_link_path("donate_pubg-mobile")[0] == "/donate/pubg-mobile"
    assert deep_link_path("donate_../x") is None
