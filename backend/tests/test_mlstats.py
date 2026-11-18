import httpx

from app.services import mlstats

RANK = {"code": 0, "data": {"records": [
    {"data": {"main_heroid": 88, "main_hero": {"data": {"name": "Masha"}}, "main_hero_win_rate": 0.58, "main_hero_appearance_rate": 0.005,
              "main_hero_ban_rate": 0.42, "sub_hero": [{"heroid": 53, "increase_win_rate": 0.03}]}},
    {"data": {"main_heroid": 1, "main_hero": {"data": {"name": "Miya"}}, "main_hero_win_rate": 0.47, "main_hero_appearance_rate": 0.02,
              "main_hero_ban_rate": 0.01, "sub_hero": []}},
]}}
RANK30 = {"code": 0, "data": {"records": [
    {"data": {"main_heroid": 88, "main_hero_win_rate": 0.55, "main_hero_appearance_rate": 0.005, "main_hero_ban_rate": 0.4}},
    {"data": {"main_heroid": 1, "main_hero_win_rate": 0.48, "main_hero_appearance_rate": 0.02, "main_hero_ban_rate": 0.01}},
]}}


def _mock(monkeypatch, fail=False):
    calls = []

    class C:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            calls.append((url, params))
            if fail:
                raise httpx.ConnectError("x")
            if "/counters" in url:
                return httpx.Response(200, json={"code": 0, "data": {"records": [{"data": {"sub_hero": [{"heroid": 21, "hero_win_rate": 0.61, "increase_win_rate": 0.05}]}}]}})
            return httpx.Response(200, json=RANK30 if params["days"] == 30 else RANK)

    monkeypatch.setattr(mlstats.httpx, "AsyncClient", C)
    mlstats._cache.clear()
    return calls


async def test_stats_tier_risers_counters_and_cache(api, monkeypatch):
    calls = _mock(monkeypatch)
    r = (await api(5).get("/mlbb/stats?rank=mythic&days=7")).json()
    assert r["items"][0] == {"hero": 88, "name": "Masha", "win": 58.0, "pick": 0.5, "ban": 42.0, "tier": "S", "mates": [{"hero": 53, "inc": 3.0}]}
    assert r["items"][1]["tier"] in ("C", "D") and r["source"] == "Rone Arena"
    n = len(calls)
    await api(5).get("/mlbb/stats?rank=mythic&days=7")
    assert len(calls) == n  # keshdan
    ris = (await api(5).get("/mlbb/risers")).json()["items"]
    assert ris[0]["hero"] == 88 and ris[0]["delta"] == 3.0
    c = (await api(5).get("/mlbb/counters/88")).json()
    assert c["counters"][0] == {"hero": 21, "win": 61.0, "inc": 5.0}


async def test_stats_unavailable_and_toggle(api, monkeypatch):
    _mock(monkeypatch, fail=True)
    assert (await api(5).get("/mlbb/stats")).status_code == 503
    assert (await api(1).put("/admin/settings", {"key": "mlbb_live_stats", "value": "off"})).status_code == 200
    assert (await api(5).get("/mlbb/stats")).status_code == 404
