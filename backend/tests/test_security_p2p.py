import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from app.security import validate_init_data
from app.services.p2p import parse_bank_message
from tests.conftest import get_balance, set_balance, give_earnings

TOKEN = "123456:TEST"


def make_init_data(user: dict, token: str = TOKEN, auth_date: int | None = None, **extra) -> str:
    data = {"user": json.dumps(user), "auth_date": str(auth_date or int(time.time())), "query_id": "AAA", **extra}
    check = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    data["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(data)


def test_init_data_valid_and_tampered():
    raw = make_init_data({"id": 42, "first_name": "Ali"})
    assert validate_init_data(raw, TOKEN)["id"] == 42
    assert validate_init_data(raw, "999:OTHER") is None
    assert validate_init_data(raw.replace("Ali", "Vali"), TOKEN) is None
    old = make_init_data({"id": 42}, auth_date=int(time.time()) - 3 * 86400)
    assert validate_init_data(old, TOKEN) is None


async def test_real_auth_header(client):
    r = await client.get("/api/me", headers={"Authorization": "tma " + make_init_data({"id": 77, "first_name": "Ali", "username": "ali"})})
    assert r.status_code == 200 and r.json()["id"] == 77
    r = await client.get("/api/me")
    assert r.status_code == 401


def test_parse_bank_messages():
    assert parse_bank_message("HUMOCARD *1234: Popolnenie scheta 50 034.00 UZS. Balans 1 250 000.00 UZS") == 50034
    assert parse_bank_message("Пополнение: +50,034.00 UZS, карта ***1234") == 50034
    assert parse_bank_message("UZCARD Kirim: 100 512 so'm. Karta *4821") == 100512
    assert parse_bank_message("P2P perevod na kartu 8600***1234 summa 20034 UZS") == 20034
    assert parse_bank_message("Oplata 50 000.00 UZS Korzinka") is None
    assert parse_bank_message("Списание 12 000 UZS") is None
    assert parse_bank_message("Salom") is None


async def test_topup_auto_match(api, ctx):
    u = api(10)
    r = await u.post("/wallet/topup", {"amount": 50_000})
    assert r.status_code == 200, r.text
    t = r.json()
    assert t["pay_amount"] == 50_000 and t["status"] == "pending"  # summa o'zgarmaydi

    sms = f"HUMOCARD *1234: Popolnenie {t['pay_amount']:,}.00 UZS".replace(",", " ")
    bad = await u.c.post("/api/p2p/incoming", json={"text": sms}, headers={"X-P2P-Secret": "wrong"})
    assert bad.status_code == 401
    r = await u.c.post("/api/p2p/incoming", json={"text": sms, "external_id": "sms-1"}, headers={"X-P2P-Secret": "test-secret"})
    assert r.json()["matched"] is True
    assert await get_balance(10) == t["pay_amount"]

    # Xuddi shu SMS qayta kelsa — ikki marta yozilmaydi.
    r = await u.c.post("/api/p2p/incoming", json={"text": sms, "external_id": "sms-1"}, headers={"X-P2P-Secret": "test-secret"})
    assert r.json().get("duplicate") is True
    assert await get_balance(10) == t["pay_amount"]
    assert (await u.get(f"/wallet/topup/{t['id']}")).json()["status"] == "paid"


async def test_unique_amounts_and_unmatched(api, ctx):
    for n in ("8600000000000001", "9860000000000002", "4073000000000003"):
        await api(1).post("/admin/p2p-cards", {"number": n, "holder": "KASSA"})
    pairs = set()
    for uid in range(100, 130):  # 3 karta × (10 000 … 10 900) = 30 ta juftlik
        r = await api(uid).post("/wallet/topup", {"amount": 10_000})
        assert r.status_code == 200, r.text
        t = r.json()
        assert t["pay_amount"] % 100 == 0 and len(t["cards"]) == 1  # faqat yaxlit summa, bitta karta
        pairs.add((t["cards"][0]["number"], t["pay_amount"]))
    assert len(pairs) == 30  # karta+summa hech qachon takrorlanmaydi
    assert {a for _, a in pairs} == {10_000 + 100 * k for k in range(10)}
    assert (await api(131).post("/wallet/topup", {"amount": 10_000})).status_code == 409  # hammasi band

    r = await api(100).c.post("/api/p2p/incoming", json={"amount": 77_777}, headers={"X-P2P-Secret": "test-secret"})
    assert r.json()["matched"] is False
    assert any("biriktirilmadi" in m[1] for m in ctx["sent"])  # admin ogohlantirildi


async def test_same_amount_on_two_cards_matched_by_card(api):
    for n in ("8600000000001111", "9860000000002222"):
        await api(1).post("/admin/p2p-cards", {"number": n, "holder": "KASSA"})
    a = (await api(140).post("/wallet/topup", {"amount": 50_000})).json()
    b = (await api(141).post("/wallet/topup", {"amount": 50_000})).json()
    assert a["pay_amount"] == b["pay_amount"] == 50_000 and a["cards"][0]["number"] != b["cards"][0]["number"]
    b4 = b["cards"][0]["number"][-4:]
    sms = f"HUMOCARD *{b4}: Popolnenie 50 000.00 UZS"
    r = await api(1).c.post("/api/p2p/incoming", json={"text": sms}, headers={"X-P2P-Secret": "test-secret"})
    assert r.json()["matched"] is True
    assert await get_balance(141) == 50_000 and await get_balance(140) == 0
    # kartasiz xabar: ikkita mos so'rov bor — avtomatik biriktirilmaydi
    c = (await api(142).post("/wallet/topup", {"amount": 50_000})).json()
    assert c["cards"][0]["number"][-4:] == b4  # bo'shagan karta qayta ishlatiladi
    r = await api(1).c.post("/api/p2p/incoming", json={"amount": 50_000, "id": "x1"}, headers={"X-P2P-Secret": "test-secret"})
    assert r.json()["matched"] is False


def test_parse_card_last4():
    from app.services.p2p import parse_card_last4

    assert parse_card_last4("HUMOCARD *5276: Popolnenie 50 000 UZS") == "5276"
    assert parse_card_last4("Karta 5614***5276 kirim 20 000 so'm") == "5276"
    assert parse_card_last4("UZCARD ••1234 +10 000 UZS") == "1234"
    assert parse_card_last4("Kirim 50 000 UZS") is None


async def test_late_payment_after_new_request(api):
    u = api(11)
    first = (await u.post("/wallet/topup", {"amount": 20_000})).json()
    await u.post("/wallet/topup", {"amount": 30_000})  # birinchisi bekor bo'ladi
    r = await u.c.post("/api/p2p/incoming", json={"amount": first["pay_amount"]}, headers={"X-P2P-Secret": "test-secret"})
    assert r.json()["matched"] is True
    assert await get_balance(11) == first["pay_amount"]


async def test_referral_bonus_once(api, client):
    await set_balance(500, 0)  # taklif qiluvchi
    raw_with_ref = make_init_data({"id": 501, "first_name": "Do'st"}, start_param="ref_500")
    h = {"Authorization": "tma " + raw_with_ref}
    await client.get("/api/me", headers=h)  # faqat /start — bonus yo'q
    assert await get_balance(500) == 0
    # Minimal summadan (10 000) kam to'ldirish — bonus yo'q
    t = (await client.post("/api/wallet/topup", json={"amount": 5_000}, headers=h)).json()
    await client.post("/api/p2p/incoming", json={"amount": t["pay_amount"]}, headers={"X-P2P-Secret": "test-secret"})
    assert await get_balance(500) == 0
    for _ in range(2):  # yetarli to'ldirishlar — bonus faqat bir marta
        t = (await client.post("/api/wallet/topup", json={"amount": 20_000}, headers=h)).json()
        await client.post("/api/p2p/incoming", json={"amount": t["pay_amount"]}, headers={"X-P2P-Secret": "test-secret"})
    assert await get_balance(500) == 2_000


async def test_withdraw_and_reject(api):
    await give_earnings(12, 100_000)
    u, admin = api(12), api(1)
    r = await u.post("/wallet/withdraw", {"amount": 60_000, "card_number": "8600 1234 5678 9012"})
    assert r.status_code == 200, r.text
    assert await get_balance(12) == 40_000
    assert (await u.post("/wallet/withdraw", {"amount": 10_000, "card_number": "8600123456789012"})).status_code == 409
    assert (await u.get("/admin/withdrawals")).status_code == 403
    w = (await admin.get("/admin/withdrawals")).json()[0]
    assert w["card"] == "8600123456789012"
    await admin.post(f"/admin/withdrawals/{w['id']}", {"action": "reject", "note": "karta xato"})
    assert await get_balance(12) == 100_000
    r = await admin.post(f"/admin/withdrawals/{w['id']}", {"action": "reject"})
    assert r.status_code == 409  # ikkinchi marta qaytarilmaydi
    assert await get_balance(12) == 100_000
