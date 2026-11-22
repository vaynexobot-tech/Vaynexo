"""MLBB buyumlari: rasmiy ro'yxat (Rone Arena akademiya API → mobilelegends.com) + narx/statlar (Fandom wiki Module:Equipment/data).

Natija: public/mlbb/items/<id>.webp (rasmiy 100px ikonka, sifat yo'qotmasdan) va public/mlbb/items.json.
Bir marta ishga tushiriladi (yangi patchdan keyin qayta): python3 scripts/fetch_mlbb_items.py
"""

import io
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent / "public" / "mlbb"
API = "https://arena.fastapicloud.dev/api/academy/equipment/expanded?size=300"
WIKI = ("https://mobile-legends.fandom.com/api.php?action=query&prop=revisions&titles=Module:Equipment/data"
        "&rvprop=content&rvslots=main&format=json")
UA = {"User-Agent": "Mozilla/5.0 (compatible; data-sync)"}
TYPES = {"Attack": "attack", "Magic": "magic", "Defense": "defense", "Movement": "boots", "Jungle": "jungle", "Roam": "roam"}


def get(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def clean(s: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", s or "")
    s = re.sub(r"</?font[^>]*>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", s).strip()


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower().replace("’", "'"))


def wiki_data() -> dict[str, dict]:
    d = json.loads(get(WIKI))
    lua = next(iter(d["query"]["pages"].values()))["revisions"][0]["slots"]["main"]["*"]
    out = {}
    for m in re.finditer(r'\[\"([^\"]+)\"\]\s*=\s*\{(.*?)\n\s*\},', lua, re.S):
        fields = dict(re.findall(r'\[\"(\w+)\"\]\s*=\s*\"((?:[^\"\\]|\\.)*)\"', m.group(2)))
        if fields.get("name"):
            out[norm(fields["name"])] = fields
    return out


def main() -> None:
    recs = [r["data"] for r in json.loads(get(API))["data"]["records"]]
    wiki = wiki_data()
    (ROOT / "items").mkdir(parents=True, exist_ok=True)
    items = []
    for x in recs:
        iid, name = int(x["equipid"]), x["equipname"].strip()
        if not re.fullmatch(r"[\x20-\x7E’'·\-]+", name) or "removed" in name.lower() or "discarded" in name.lower():
            continue  # eskirgan / xitoycha nomli yozuvlar
        url = urllib.parse.parse_qs(urllib.parse.urlparse(x["equipicon"]).query).get("url", [x["equipicon"]])[0]
        try:
            im = Image.open(io.BytesIO(get(url))).convert("RGBA")
            im.save(ROOT / "items" / f"{iid}.webp", "WEBP", quality=92, method=6)  # 100px rasmiy ikonka, ko'zga farqsiz
        except Exception as e:  # noqa: BLE001
            print("rasm yo'q:", name, e, file=sys.stderr)
            continue
        base = re.sub(r"^\w+ Hunter's ", "", name.split(" - ")[0].split("- ")[0]).strip()  # «Arcane Boots - Favor» → «Arcane Boots»
        if name in ("Allow Throw", "Throw Forbidden"):
            continue  # Jawhead maxsus sozlamalari — buyum emas
        alias = {"demonboots": "demonshoes", "magicboots": "magicshoes"}.get(norm(base), norm(base))  # wiki nomi boshqacha
        w = wiki.get(norm(name)) or {k: v for k, v in wiki.get(alias, {}).items() if k in ("price", "bonus", "caption")}
        if not w and not x.get("equiptips"):
            continue  # maxsus (masalan, Jawhead «Allow Throw») — do'konda sotilmaydi
        stats = clean(x.get("equiptips", "")) or w.get("bonus", "")
        items.append({
            "id": iid, "name": name, "type": TYPES.get(x.get("equiptypename", ""), "other"),
            "price": int(w["price"]) if w.get("price", "").isdigit() and int(w["price"]) > 0 else None,
            "stats": [s.strip() for s in re.split(r"\n|,\s*(?=\+)", stats) if s.strip()],
            "unique": w.get("unique") or None,
            "passive": clean(x.get("equipskilldesc", "")) or w.get("passive") or None,
            "caption": w.get("caption") or None,
            "recipe": [r.strip() for r in (w.get("recipe") or "").split(",") if r.strip()],
        })
    items.sort(key=lambda i: (-(i["price"] or 0), i["name"]))
    (ROOT / "items.json").write_text(json.dumps(items, ensure_ascii=False, separators=(",", ":")))
    print(f"{len(items)} ta buyum, narxi bor: {sum(1 for i in items if i['price'])}")


if __name__ == "__main__":
    main()
