import io

from PIL import Image

from tests.conftest import set_balance


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), "blue").save(buf, "PNG")
    return buf.getvalue()


async def test_upload_stored_in_db_and_served(api, client):
    await set_balance(5, 0)
    r = await client.post("/api/media", files={"file": ("a.png", _png(), "image/png")}, headers={"X-Dev-User": "5"})
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert r.json()["type"] == "image" and url.startswith("/media/db/") and url.endswith(".webp")
    g = await client.get(url)  # tokensiz — <img> shunday so'raydi
    assert g.status_code == 200 and g.headers["content-type"] == "image/webp"
    assert "immutable" in g.headers["cache-control"] and Image.open(io.BytesIO(g.content)).size == (300, 200)
    assert (await client.get("/media/db/yoq-fayl-12345678.webp")).status_code == 404
    assert (await client.get("/media/db/..%2Fetc%2Fpasswd")).status_code in (404, 422)


async def test_video_range_and_limits(api, client):
    await set_balance(6, 0)
    data = bytes(range(256)) * 40
    r = await client.post("/api/media", files={"file": ("v.mp4", data, "video/mp4")}, headers={"X-Dev-User": "6"})
    url = r.json()["url"]
    assert r.json()["type"] == "video"
    full = await client.get(url)
    assert full.content == data and full.headers["accept-ranges"] == "bytes"
    part = await client.get(url, headers={"Range": "bytes=10-19"})
    assert part.status_code == 206 and part.content == data[10:20] and part.headers["content-range"] == f"bytes 10-19/{len(data)}"
    tail = await client.get(url, headers={"Range": "bytes=-5"})
    assert tail.status_code == 206 and tail.content == data[-5:]
    assert (await client.get(url, headers={"Range": "bytes=999999-"})).status_code == 416
    bad = await client.post("/api/media", files={"file": ("x.txt", b"hi", "text/plain")}, headers={"X-Dev-User": "6"})
    assert bad.status_code == 400
    corrupt = await client.post("/api/media", files={"file": ("a.png", b"not an image", "image/png")}, headers={"X-Dev-User": "6"})
    assert corrupt.status_code == 400
