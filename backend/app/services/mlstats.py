"""MLBB tirik statistikasi (g'alaba / tanlov / ban foizi, tier, kuchayganlar, counter).

Manba: Rone Arena (https://arena.rone.dev) — mobilelegends.com ochiq ma'lumotini qayta beruvchi jamoat API'si.
So'rovlar kam bo'lsin: har bir javob serverda keshlanadi (6 soat), API ishlamasa eski nusxa qaytariladi.
"""

import logging
import time

import httpx

from app.errors import AppError

log = logging.getLogger(__name__)

BASES = ("https://arena.rone.dev/api", "https://arena.fastapicloud.dev/api")
RANKS = ("all", "epic", "legend", "mythic", "honor", "glory")
TTL = 6 * 3600
_cache: dict[str, tuple[float, object]] = {}


async def _get(path: str, params: dict) -> dict:
    key = path + "?" + "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]  # type: ignore[return-value]
    last: Exception | None = None
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "VaynexoBot/1.0 (+https://t.me/vaynexobot)"}) as c:
        for base in BASES:  # asosiy xost band bo'lsa — zaxira xost
            try:
                r = await c.get(base + path, params=params)
                if r.status_code == 200:
                    data = r.json()
                    if data.get("code") == 0:
                        _cache[key] = (time.time(), data)
                        return data
                last = RuntimeError(f"http {r.status_code}")
            except (httpx.HTTPError, ValueError) as e:
                last = e
    if hit:  # eskirgan bo'lsa ham bor narsani beramiz
        log.warning("MLBB statistika yangilanmadi, eski nusxa: %s", last)
        return hit[1]  # type: ignore[return-value]
    raise AppError("stats_unavailable", "Statistika vaqtincha mavjud emas, birozdan so'ng urinib ko'ring", 503)


def _rows(data: dict) -> list[dict]:
    return [r.get("data") or {} for r in ((data.get("data") or {}).get("records") or [])]


def _tier(win: float, pick: float, ban: float) -> str:
    """Oddiy meta bahosi: g'alaba foizi asosiy, mashhurlik va ban — qo'shimcha."""
    score = (win - 0.5) * 100 + min(pick * 100, 3) * 0.8 + min(ban * 100, 40) * 0.08
    return "S" if score >= 5 else "A" if score >= 2.5 else "B" if score >= 0 else "C" if score >= -3 else "D"


async def rank_stats(rank: str = "all", days: int = 7) -> list[dict]:
    if rank not in RANKS:
        rank = "all"
    days = days if days in (1, 3, 7, 15, 30) else 7
    data = await _get("/heroes/rank", {"days": days, "rank": rank, "sort_field": "win_rate", "sort_order": "desc", "size": 200, "index": 1})
    out = []
    for d in _rows(data):
        try:
            hid = int(d.get("main_heroid"))
        except (TypeError, ValueError):
            continue
        win, pick, ban = float(d.get("main_hero_win_rate") or 0), float(d.get("main_hero_appearance_rate") or 0), float(d.get("main_hero_ban_rate") or 0)
        out.append({"hero": hid, "name": ((d.get("main_hero") or {}).get("data") or {}).get("name") or "",
                    "win": round(win * 100, 2), "pick": round(pick * 100, 2), "ban": round(ban * 100, 2), "tier": _tier(win, pick, ban),
                    "mates": [{"hero": int(s["heroid"]), "inc": round(float(s.get("increase_win_rate") or 0) * 100, 2)}
                              for s in (d.get("sub_hero") or []) if str(s.get("heroid", "")).isdigit()][:3]})
    return out


async def risers(rank: str = "all", limit: int = 10) -> list[dict]:
    """«Kuchayganlar»: oxirgi 7 kunlik g'alaba foizi 30 kunlikdan qanchalik oshgan."""
    week = {x["hero"]: x for x in await rank_stats(rank, 7)}
    month = {x["hero"]: x for x in await rank_stats(rank, 30)}
    rows = [{**w, "delta": round(w["win"] - month[h]["win"], 2)} for h, w in week.items() if h in month and w["pick"] >= 0.05]
    return sorted(rows, key=lambda x: x["delta"], reverse=True)[:limit]


async def counters(hero_id: int, rank: str = "all", days: int = 7) -> dict:
    """Shu qahramonga qarshi kuchli qahramonlar (raqib sifatida g'alaba foizi)."""
    if rank not in RANKS:
        rank = "all"
    data = await _get(f"/heroes/{int(hero_id)}/counters", {"days": days if days in (1, 3, 7, 15, 30) else 7, "rank": rank})
    rows = _rows(data)
    d = rows[0] if rows else {}
    subs = [{"hero": int(s["heroid"]), "win": round(float(s.get("hero_win_rate") or 0) * 100, 2),
             "inc": round(float(s.get("increase_win_rate") or 0) * 100, 2)}
            for s in (d.get("sub_hero") or []) if str(s.get("heroid", "")).isdigit()]
    return {"hero": hero_id, "counters": subs[:6]}
