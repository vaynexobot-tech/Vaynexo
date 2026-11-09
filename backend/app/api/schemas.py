"""Javob shakllari (dict) — frontend uchun kerakli maydonlargina."""

from app.models import BoostOrder, Chat, Deal, DonateOrder, DonatePackage, LedgerEntry, Listing, Message, Topup, TgOrder, Tournament, User, Withdrawal


def iso(dt) -> str | None:
    return dt.isoformat() if dt else None


def user_public(u: User) -> dict:
    return {
        "id": u.id,
        "name": u.first_name,
        "username": u.username,
        "rating": round(u.rating_sum / u.rating_count, 1) if u.rating_count else None,
        "rating_count": u.rating_count,
    }


def user_private(u: User) -> dict:
    return {
        **user_public(u),
        "balance": u.balance,
        "tickets": u.tickets,
        "lang": u.lang,
        "phone": u.phone,
        "ml_id": u.ml_id,
        "bio": u.bio,
        "is_admin": u.is_admin,
    }


def package(p: DonatePackage) -> dict:
    return {"id": p.id, "game": p.game, "name": p.name, "diamonds": p.diamonds, "bonus": p.bonus,
            "price": p.price, "is_hot": p.is_hot, "is_active": p.is_active, "sku": p.provider_sku, "sort": p.sort}


def donate_order(o: DonateOrder) -> dict:
    return {"id": o.id, "ref": f"VX-D{o.id}", "game": o.game, "title": o.title, "player_id": o.player_id,
            "zone_id": o.zone_id, "price": o.price, "status": o.status, "error": o.error,
            "created_at": iso(o.created_at), "finished_at": iso(o.finished_at)}


def listing_card(item: Listing) -> dict:
    return {
        "id": item.id, "game": item.game, "title": item.title, "rank": item.rank, "server": item.server,
        "collection_level": item.collection_level, "skins": item.skins, "heroes": item.heroes, "price": item.price,
        "cover": next((m["url"] for m in item.media if m.get("type") == "image"), None),
        "status": item.status, "created_at": iso(item.created_at),
    }


def listing_full(item: Listing) -> dict:
    return {**listing_card(item), "description": item.description, "media": item.media, "views": item.views,
            "reject_reason": item.reject_reason, "seller": user_public(item.seller)}


def chat(c: Chat, me: int) -> dict:
    return {"id": c.id, "listing": listing_card(c.listing), "role": "buyer" if c.buyer_id == me else "seller",
            "buyer_id": c.buyer_id, "seller_id": c.seller_id, "last_message_at": iso(c.last_message_at)}


def message(m: Message) -> dict:
    return {"id": m.id, "sender_id": m.sender_id, "text": m.text, "created_at": iso(m.created_at)}


def deal(d: Deal, me: int, credentials: str | None = None) -> dict:
    return {
        "id": d.id, "listing": listing_card(d.listing), "price": d.price, "commission": d.commission,
        "status": d.status, "role": "buyer" if d.buyer_id == me else ("seller" if d.seller_id == me else "admin"),
        "chat_id": d.chat_id, "buyer_id": d.buyer_id, "seller_id": d.seller_id, "credentials": credentials,
        "delivered_at": iso(d.delivered_at), "auto_release_at": iso(d.auto_release_at),
        "dispute_reason": d.dispute_reason, "resolution": d.resolution, "created_at": iso(d.created_at),
    }


def topup(t: Topup, card: str, holder: str) -> dict:
    return {"id": t.id, "requested_amount": t.requested_amount, "pay_amount": t.pay_amount, "status": t.status,
            "expires_at": iso(t.expires_at), "paid_at": iso(t.paid_at), "card_number": card, "card_holder": holder,
            "created_at": iso(t.created_at)}


def ledger(e: LedgerEntry) -> dict:
    return {"id": e.id, "amount": e.amount, "balance_after": e.balance_after, "kind": e.kind, "note": e.note,
            "created_at": iso(e.created_at)}


def withdrawal(w: Withdrawal, full_card: bool = False) -> dict:
    return {"id": w.id, "user_id": w.user_id, "amount": w.amount,
            "card": w.card_number if full_card else "•••• " + w.card_number[-4:], "card_holder": w.card_holder,
            "status": w.status, "admin_note": w.admin_note, "created_at": iso(w.created_at)}


def tg_order(o: TgOrder) -> dict:
    return {"id": o.id, "ref": f"VX-T{o.id}", "kind": o.kind, "title": o.title, "target_username": o.target_username,
            "details": o.details, "price": o.price, "status": o.status, "admin_note": o.admin_note,
            "user_id": o.user_id, "created_at": iso(o.created_at)}


def boost(o: BoostOrder) -> dict:
    return {"id": o.id, "ref": f"VX-B{o.id}", "game": o.game, "current_rank": o.current_rank,
            "target_rank": o.target_rank, "stars": o.stars, "lane": o.lane, "note": o.note,
            "login_method": o.login_method, "price": o.price, "status": o.status, "booster_name": o.booster_name,
            "user_id": o.user_id, "created_at": iso(o.created_at), "finished_at": iso(o.finished_at)}


def tournament(t: Tournament, joined: bool = False) -> dict:
    return {"id": t.id, "title": t.title, "game": t.game, "prize_fund": t.prize_fund, "entry_fee": t.entry_fee,
            "max_players": t.max_players, "players_count": t.players_count, "starts_at": iso(t.starts_at),
            "rules": t.rules, "status": t.status, "joined": joined}
