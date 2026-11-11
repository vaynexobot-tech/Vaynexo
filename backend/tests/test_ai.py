from app.config import settings
from app.services import ai
from tests.test_flows import LISTING


async def _publish(api, **over) -> int:
    r = await api(40).post("/listings", {**LISTING, **over})
    lid = r.json()["id"]
    await api(1).post(f"/admin/listings/{lid}/moderate", {"approve": True})
    return lid


async def test_ai_off_without_key(api, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert (await api(50).get("/ai/status")).json()["enabled"] is False
    r = await api(50).post("/ai/ask", {"text": "Mythic akkaunt kerak"})
    assert r.status_code == 503 and r.json()["error"] == "ai_off"


async def test_ai_search_uses_real_listings_and_limit(api, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test")
    monkeypatch.setattr(settings, "ai_daily_limit", 2)
    cheap = await _publish(api, price=380_000, skins=58)
    await _publish(api, price=900_000, skins=120)  # narxi oshib ketadi
    await _publish(api, price=300_000, skins=10)  # skin kam
    await _publish(api, rank="Legend", price=200_000, skins=80)  # rank boshqa
    seen = {}

    async def fake_call(system, messages, schema, max_tokens=2000):
        seen["messages"] = messages
        return {"reply": "Mos e'lonlar:", "search": True, "game": "ML", "ranks": ["Mythic"], "min_skins": 50,
                "min_price": 0, "max_price": 500_000, "sort": "best"}

    monkeypatch.setattr(ai, "_call", fake_call)
    r = await api(50).post("/ai/ask", {"text": "Mythic, 50+ skin, 500k gacha",
                                       "history": [{"role": "ai", "text": "Salom!"}, {"role": "user", "text": "salom"},
                                                   {"role": "ai", "text": "Qanday yordam?"}]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert [x["id"] for x in d["listings"]] == [cheap] and d["left"] == 1
    # tarix user bilan boshlanadi va rollar almashadi
    roles = [m["role"] for m in seen["messages"]]
    assert roles[0] == "user" and roles[-1] == "user" and all(a != b for a, b in zip(roles, roles[1:]))
    assert (await api(50).get("/ai/status")).json()["left"] == 1
    await api(50).post("/ai/ask", {"text": "yana"})
    r = await api(50).post("/ai/ask", {"text": "yana"})
    assert r.status_code == 429 and r.json()["error"] == "ai_limit"


async def test_ai_nothing_found_and_plain_answer(api, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test")

    async def fake_search(system, messages, schema, max_tokens=2000):
        return {"reply": "x", "search": True, "game": "MC", "ranks": [], "min_skins": 0, "min_price": 0,
                "max_price": 1000, "sort": "cheap"}

    monkeypatch.setattr(ai, "_call", fake_search)
    d = (await api(51).post("/ai/ask", {"text": "arzon MC"})).json()
    assert d["listings"] == [] and "topilmadi" in d["reply"]

    async def fake_info(system, messages, schema, max_tokens=2000):
        return {"reply": "Hamyon → To'ldirish.", "search": False, "game": "any", "ranks": [], "min_skins": 0,
                "min_price": 0, "max_price": 0, "sort": "best"}

    monkeypatch.setattr(ai, "_call", fake_info)
    d = (await api(51).post("/ai/ask", {"text": "qanday to'ldiraman"})).json()
    assert d == {"reply": "Hamyon → To'ldirish.", "listings": [], "left": d["left"]}


async def test_ai_describe(api, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "test")

    async def fake(system, messages, schema, max_tokens=2000):
        assert "Mobile Legends" in messages[0]["content"]
        return {"title": "Mythic akkaunt · 120 skin", "description": "Toza akkaunt."}

    monkeypatch.setattr(ai, "_call", fake)
    r = await api(52).post("/ai/describe", {"game": "ML", "rank": "Mythic", "skins": 120})
    assert r.json()["title"] == "Mythic akkaunt · 120 skin"
