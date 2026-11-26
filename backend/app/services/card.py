"""O'yinchi kartasi: ulashish uchun rasm (nik, rank, liniya, sevimli qahramonlar, VAY, Draft ELO) + taklif havolasi QR'da."""

import io

from app.services import mlbb
from app.services.shops import _latin

RANK_LABEL = {"warrior": "Warrior", "elite": "Elite", "master": "Master", "grandmaster": "Grandmaster", "epic": "Epic", "legend": "Legend",
              "mythic": "Mythic", "honor": "Mythical Honor", "glory": "Mythical Glory", "immortal": "Mythical Immortal"}


def player_card_png(nick: str, rank: str, lane: str, heroes: list[int], vay_name: str, vay_xp: int, elo: int, streak: int,
                    place: int | None, link: str) -> bytes:
    import segno
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1080, 1350
    img = Image.new("RGB", (W, H), "#0d0e13")
    d = ImageDraw.Draw(img)
    for y in range(H):
        k = y / H
        d.line([(0, y), (W, y)], fill=(int(16 + 30 * (1 - k)), int(14 + 14 * (1 - k)), int(24 + 46 * (1 - k))))
    d.rounded_rectangle([60, 60, W - 60, H - 60], radius=48, outline="#9b6bff", width=4)
    f = lambda s: ImageFont.load_default(size=s)  # noqa: E731

    def center(text: str, y: int, size: int, fill: str, maxw: int = W - 200) -> int:
        font = f(size)
        while d.textlength(text, font=font) > maxw and size > 24:
            size -= 4
            font = f(size)
        d.text(((W - d.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)
        return y + size + 22

    y = center("VAYNEXO · MLBB KARTA".replace("·", "-"), 110, 36, "#9b6bff")
    y = center(_latin(nick) or "Player", y + 30, 100, "#ffffff")
    sub = " - ".join(x for x in (RANK_LABEL.get(rank, rank.title() if rank else ""), lane.upper() if lane else "") if x)
    if sub:
        y = center(sub, y, 44, "#ffd60a")
    # sevimli qahramonlar
    img_dir = mlbb._img_dir()
    heroes = [h for h in heroes if h in mlbb.heroes()][:3]
    if heroes:
        size, gap = 220, 40
        x0 = (W - (size * len(heroes) + gap * (len(heroes) - 1))) // 2
        y0 = y + 40
        for i, hid in enumerate(heroes):
            x = x0 + i * (size + gap)
            ph = None
            if img_dir:
                try:
                    ph = Image.open(img_dir / f"{hid}.webp").convert("RGB").resize((size, size))
                except Exception:  # noqa: BLE001
                    ph = None
            mask = Image.new("L", (size, size), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, size - 1, size - 1], fill=255)
            if ph is None:
                ph = Image.new("RGB", (size, size), "#2a2c44")
            img.paste(ph, (x, y0), mask)
            d.ellipse([x, y0, x + size - 1, y0 + size - 1], outline="#9b6bff", width=5)
            name = _latin(mlbb.heroes()[hid]["name"])
            fw = d.textlength(name, font=f(30))
            d.text((x + (size - fw) / 2, y0 + size + 14), name, font=f(30), fill="#c9cde0")
        y = y0 + size + 70
    # ko'rsatkichlar
    stats = [("VAY", f"{vay_name} {vay_xp}"), ("DRAFT ELO", str(elo)), ("SERIYA", f"{streak} kun")]
    if place:
        stats.append(("ARENA", f"#{place}"))
    cw = (W - 160) // len(stats)
    y += 10
    for i, (a, b) in enumerate(stats):
        cx = 80 + i * cw + cw // 2
        for txt, size, col, dy in ((b, 40, "#ffffff", 0), (a, 26, "#9aa0b4", 52)):
            font = f(size)
            while d.textlength(txt, font=font) > cw - 20 and size > 18:
                size -= 2
                font = f(size)
            d.text((cx - d.textlength(txt, font=font) / 2, y + dy), txt, font=font, fill=col)
    y += 120
    qr = segno.make(link, error="m")
    n = qr.symbol_size(border=0)[0]
    cell, pad = 8, 20
    side = n * cell + pad * 2
    qx, qy = (W - side) // 2, max(y + 10, H - 60 - side - 130)
    d.rounded_rectangle([qx, qy, qx + side, qy + side], radius=22, fill="#ffffff")
    for r, row in enumerate(qr.matrix):
        for c, v in enumerate(row):
            if v:
                d.rectangle([qx + pad + c * cell, qy + pad + r * cell, qx + pad + (c + 1) * cell - 1, qy + pad + (r + 1) * cell - 1], fill="#111111")
    center("Mening kartam: VAYNEXO'da o'ynang", qy + side + 18, 34, "#ffffff")
    out = io.BytesIO()
    img.save(out, "PNG", optimize=True)
    return out.getvalue()
