"""Ma'lumotlar bazasi modellari.

Pul har doim butun so'mda (BigInteger) saqlanadi. Balansning har bir o'zgarishi
LedgerEntry jadvaliga yoziladi va `idem_key` orqali ikki marta yozilmaydi.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("balance >= 0", name="balance_non_negative"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Telegram user id
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(128), default="")
    lang: Mapped[str] = mapped_column(String(2), default="uz")
    phone: Mapped[str | None] = mapped_column(String(32))
    ml_id: Mapped[str | None] = mapped_column(String(32))
    bio: Mapped[str | None] = mapped_column(String(300))
    balance: Mapped[int] = mapped_column(BigInteger, default=0)
    tickets: Mapped[int] = mapped_column(Integer, default=0)  # konkurs biletlari
    rating_sum: Mapped[int] = mapped_column(Integer, default=0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    referral_paid: Mapped[bool] = mapped_column(Boolean, default=False)


class LedgerEntry(TimestampMixin, Base):
    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)  # + kirim, - chiqim
    balance_after: Mapped[int] = mapped_column(BigInteger)
    kind: Mapped[str] = mapped_column(String(32))
    ref_type: Mapped[str | None] = mapped_column(String(32))
    ref_id: Mapped[int | None] = mapped_column(BigInteger)
    note: Mapped[str | None] = mapped_column(String(300))
    idem_key: Mapped[str] = mapped_column(String(120), unique=True)


# ---------------------------------------------------------------- P2P to'ldirish
class Topup(TimestampMixin, Base):
    __tablename__ = "topups"
    __table_args__ = (Index("ix_topups_pending_amount", "pay_amount", "status"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    requested_amount: Mapped[int] = mapped_column(BigInteger)
    pay_amount: Mapped[int] = mapped_column(BigInteger)  # noyob summa, masalan 50 034
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | paid | expired | cancelled
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    incoming_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("incoming_payments.id"))


class IncomingPayment(TimestampMixin, Base):
    """Kartaga tushgan kirim (SMS-forwarder, bank xabari yoki admin kiritgan)."""

    __tablename__ = "incoming_payments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    amount: Mapped[int] = mapped_column(BigInteger, index=True)
    source: Mapped[str] = mapped_column(String(32))  # sms | bot_forward | admin
    raw_text: Mapped[str | None] = mapped_column(Text)
    dedupe_key: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="unmatched")  # matched | unmatched | ignored
    topup_id: Mapped[int | None] = mapped_column(BigInteger)


class Withdrawal(TimestampMixin, Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    card_number: Mapped[str] = mapped_column(String(32))
    card_holder: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending | paid | rejected
    admin_note: Mapped[str | None] = mapped_column(String(300))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------- Donat
class DonatePackage(Base):
    __tablename__ = "donate_packages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    game: Mapped[str] = mapped_column(String(8), index=True)  # ML | MC
    name: Mapped[str] = mapped_column(String(64))  # "172 almaz", "Haftalik propusk"
    diamonds: Mapped[int] = mapped_column(Integer, default=0)
    bonus: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[int] = mapped_column(BigInteger)
    provider_sku: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_hot: Mapped[bool] = mapped_column(Boolean, default=False)
    sort: Mapped[int] = mapped_column(Integer, default=0)


class DonateOrder(TimestampMixin, Base):
    __tablename__ = "donate_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    package_id: Mapped[int] = mapped_column(Integer, ForeignKey("donate_packages.id"))
    game: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(64))
    player_id: Mapped[str] = mapped_column(String(32))
    zone_id: Mapped[str] = mapped_column(String(16), default="")
    price: Mapped[int] = mapped_column(BigInteger)
    # processing | done | refunded
    status: Mapped[str] = mapped_column(String(16), default="processing", index=True)
    provider_ref: Mapped[str | None] = mapped_column(String(128))
    error: Mapped[str | None] = mapped_column(String(500))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    package: Mapped[DonatePackage] = relationship(lazy="selectin")


# ---------------------------------------------------------------- Akkaunt savdo
class Listing(TimestampMixin, Base):
    __tablename__ = "listings"
    __table_args__ = (Index("ix_listings_feed", "status", "game", "price"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    seller_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    game: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(120))
    rank: Mapped[str] = mapped_column(String(32))
    server: Mapped[str] = mapped_column(String(32), default="")
    collection_level: Mapped[str] = mapped_column(String(32), default="")
    skins: Mapped[int] = mapped_column(Integer, default=0)
    heroes: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(Text, default="")
    media: Mapped[list] = mapped_column(JSONB, default=list)  # [{"type": "image"|"video", "url": "..."}]
    # moderation | active | rejected | reserved | sold | closed
    status: Mapped[str] = mapped_column(String(16), default="moderation", index=True)
    reject_reason: Mapped[str | None] = mapped_column(String(300))
    views: Mapped[int] = mapped_column(Integer, default=0)
    vip_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # pullik: ro'yxat tepasida

    seller: Mapped[User] = relationship(lazy="selectin")


class Chat(TimestampMixin, Base):
    __tablename__ = "chats"
    __table_args__ = (UniqueConstraint("listing_id", "buyer_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("listings.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    seller_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listing: Mapped[Listing] = relationship(lazy="selectin")


class Message(TimestampMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_chat", "chat_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.id"))
    sender_id: Mapped[int | None] = mapped_column(BigInteger)  # None = tizim xabari
    text: Mapped[str] = mapped_column(Text)


class Deal(TimestampMixin, Base):
    """Garantli bitim: pul xaridordan yechilib, tasdiqlangunga qadar platformada turadi."""

    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("listings.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    seller_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chats.id"))
    price: Mapped[int] = mapped_column(BigInteger)
    commission: Mapped[int] = mapped_column(BigInteger)
    # paid -> delivered -> completed | disputed -> completed/refunded | cancelled(refunded)
    status: Mapped[str] = mapped_column(String(16), default="paid", index=True)
    credentials_enc: Mapped[str | None] = mapped_column(Text)  # shifrlangan login/parol
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    auto_release_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    dispute_reason: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(String(300))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    listing: Mapped[Listing] = relationship(lazy="selectin")


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("deals.id"), unique=True)
    from_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    to_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    score: Mapped[int] = mapped_column(Integer)
    tags: Mapped[list] = mapped_column(JSONB, default=list)
    text: Mapped[str] = mapped_column(String(500), default="")


# ---------------------------------------------------------------- TG xizmatlar
class TgOrder(TimestampMixin, Base):
    __tablename__ = "tg_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # premium | stars | gift | nft
    title: Mapped[str] = mapped_column(String(120))
    target_username: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    price: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(16), default="processing", index=True)  # processing|done|refunded
    admin_note: Mapped[str | None] = mapped_column(String(300))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------- Boost
class BoostOrder(TimestampMixin, Base):
    __tablename__ = "boost_orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    game: Mapped[str] = mapped_column(String(8))
    current_rank: Mapped[str] = mapped_column(String(32))
    target_rank: Mapped[str] = mapped_column(String(32))
    stars: Mapped[int] = mapped_column(Integer, default=0)
    lane: Mapped[str] = mapped_column(String(16), default="")
    note: Mapped[str] = mapped_column(String(500), default="")
    login_method: Mapped[str] = mapped_column(String(16))  # moonton | google | telegram | whatsapp
    credentials_enc: Mapped[str | None] = mapped_column(Text)
    price: Mapped[int] = mapped_column(BigInteger)
    # searching | accepted | in_progress | done | refunded
    status: Mapped[str] = mapped_column(String(16), default="searching", index=True)
    booster_id: Mapped[int | None] = mapped_column(BigInteger)
    booster_name: Mapped[str | None] = mapped_column(String(64))
    group_message_id: Mapped[int | None] = mapped_column(BigInteger)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ---------------------------------------------------------------- Arena
class Tournament(TimestampMixin, Base):
    __tablename__ = "tournaments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    game: Mapped[str] = mapped_column(String(8))
    prize_fund: Mapped[int] = mapped_column(BigInteger)
    entry_fee: Mapped[int] = mapped_column(BigInteger, default=0)
    max_players: Mapped[int] = mapped_column(Integer)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rules: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open | running | finished
    players_count: Mapped[int] = mapped_column(Integer, default=0)


class TournamentEntry(TimestampMixin, Base):
    __tablename__ = "tournament_entries"
    __table_args__ = (UniqueConstraint("tournament_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tournament_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tournaments.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    nick: Mapped[str] = mapped_column(String(64))
    game_id: Mapped[str] = mapped_column(String(32))
    server: Mapped[str] = mapped_column(String(16), default="")
    tg_username: Mapped[str] = mapped_column(String(64), default="")


# ---------------------------------------------------------------- Sozlamalar (admin paneldan o'zgaradi)
class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(500))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Favorite(TimestampMixin, Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "listing_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    listing_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("listings.id"), index=True)


# ---------------------------------------------------------------- Account ijara
class RentListing(TimestampMixin, Base):
    """Ijaraga qo'yilgan akkaunt. Kirish ma'lumotlari egasidan oldindan olinadi (shifrlangan)
    va faqat to'lagan ijarachiga, ijara davomida ko'rsatiladi."""

    __tablename__ = "rent_listings"
    __table_args__ = (Index("ix_rent_feed", "status", "price_per_hour"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    game: Mapped[str] = mapped_column(String(8))
    title: Mapped[str] = mapped_column(String(120))
    rank: Mapped[str] = mapped_column(String(32))
    server: Mapped[str] = mapped_column(String(32), default="")
    skins: Mapped[int] = mapped_column(Integer, default=0)
    heroes: Mapped[int] = mapped_column(Integer, default=0)
    price_per_hour: Mapped[int] = mapped_column(BigInteger)
    description: Mapped[str] = mapped_column(Text, default="")
    media: Mapped[list] = mapped_column(JSONB, default=list)
    credentials_enc: Mapped[str] = mapped_column(Text)
    # moderation | active | rejected | closed
    status: Mapped[str] = mapped_column(String(16), default="moderation", index=True)
    reject_reason: Mapped[str | None] = mapped_column(String(300))
    busy_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(lazy="selectin")


class Rental(TimestampMixin, Base):
    """Ijara: pul va depozit garantda. active -> ended (egasi tekshiradi) -> completed | disputed -> completed."""

    __tablename__ = "rentals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    listing_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("rent_listings.id"), index=True)
    renter_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    hours: Mapped[int] = mapped_column(Integer)
    price: Mapped[int] = mapped_column(BigInteger)
    deposit: Mapped[int] = mapped_column(BigInteger)
    commission: Mapped[int] = mapped_column(BigInteger)
    # active | ended | completed | disputed | refunded
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    review_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    dispute_by: Mapped[str | None] = mapped_column(String(8))  # owner | renter
    dispute_reason: Mapped[str | None] = mapped_column(Text)
    resolution: Mapped[str | None] = mapped_column(String(300))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    listing: Mapped[RentListing] = relationship(lazy="selectin")
