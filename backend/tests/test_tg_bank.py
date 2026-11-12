from types import SimpleNamespace

from app.services import tg_bank
from app.services.p2p import parse_bank_message
from tests.conftest import get_balance

HUMO_IN = "🟢 Пополнение\n➕ 50 000.00 UZS\n📍 P2P HUMO2HUMO>TOSHKENT\n💳 HUMOCARD *0000\n🕓 12:30 12.11.26\n💰 1 250 000.00 UZS"
HUMO_OUT = "🔴 Оплата\n➖ 30 000.00 UZS\n📍 P2P PAYME>TOSHKENT\n💳 HUMOCARD *0000\n🕓 12:31 12.11.26\n💰 1 220 000.00 UZS"
UZCARD_IN = "💸 Popolnenie ✅\n➕ 75 000,00 UZS\n📍 UZCARD P2P\n💳 ***0000\n🕓 12.11.26 12:40\n💵 Balans: 300 000,00 UZS"
UZCARD_OUT = "🔴 Perevod s karty\n➖ 10 000,00 UZS\n💳 ***0000"


def test_parse_bank_bot_formats():
    assert parse_bank_message(HUMO_IN) == 50_000
    assert parse_bank_message(HUMO_OUT) is None
    assert parse_bank_message(UZCARD_IN) == 75_000
    assert parse_bank_message(UZCARD_OUT) is None


async def test_bank_bot_messages_credit_topup(api):
    t = (await api(150).post("/wallet/topup", {"amount": 50_000})).json()
    assert t["pay_amount"] == 50_000
    msgs = [SimpleNamespace(id=10, message=HUMO_OUT, out=False), SimpleNamespace(id=11, message=HUMO_IN, out=False)]
    assert await tg_bank.process_messages("HUMOcardbot", msgs) == 1
    assert await get_balance(150) == 50_000
    # takroriy xabar ikki marta hisoblanmaydi
    assert await tg_bank.process_messages("HUMOcardbot", msgs) == 0
    assert await get_balance(150) == 50_000


async def test_admin_tg_bank_settings(api):
    r = await api(1).get("/admin/tg-bank")
    assert r.status_code == 200 and r.json()["bots"] == ["HUMOcardbot", "CardXabarBot"]
    assert r.json()["logged_in"] is False
    assert (await api(5).get("/admin/tg-bank")).status_code == 403
    r = await api(1).put("/admin/tg-bank/bots", {"bots": ["@HUMOcardbot", "CardXabarBot", "https://t.me/KapitalVisaBot"]})
    assert r.json()["bots"] == ["HUMOcardbot", "CardXabarBot", "KapitalVisaBot"]
    assert (await api(1).put("/admin/tg-bank/bots", {"bots": ["yomon nom!"]})).status_code == 400
    assert (await api(1).post("/admin/tg-bank/api", {"api_id": "abc", "api_hash": "x"})).status_code == 400
    r = await api(1).post("/admin/tg-bank/api", {"api_id": "12345", "api_hash": "a" * 32})
    assert r.json()["api_ready"] is True
