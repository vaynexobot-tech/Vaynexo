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
    # Identifikatsiya: none | pending | verified | rejected
    kyc_status: Mapped[str] = mapped_column(String(16), default="none", server_default="none", index=True)
    kyc_note: Mapped[str | None] = mapped_column(String(300))
    kyc_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Xavfsizlik: PIN (scrypt xeshi), pin_ver o'zgarsa eski tokenlar bekor bo'ladi; biometrik kalit xeshi
    pin_hash: Mapped[str | None] = mapped_column(String(200))
    pin_ver: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    bio_hash: Mapped[str | None] = mapped_column(String(128))
    notify_chat: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    notify_tour: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # Arena va Hamkor: ball (pulga almashtirilmaydi) va almashtirilgan imtiyozlar
    points: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    vip_credit_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tournament_passes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    boost_coupon_percent: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    badge: Mapped[str | None] = mapped_column(String(32))


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
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | checking | paid | rejected | expired | cancelled
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    incoming_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("incoming_payments.id"))
    # «To'ladim» bosilgach: checking; admin yoki bank xabari tasdiqlaydi
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    has_receipt: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    review_sent: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")  # adminga eslatma ketganmi
    reject_reason: Mapped[str | None] = mapped_column(String(300))


class P2PCard(TimestampMixin, Base):
    """To'lov qabul qilinadigan kartalar (admin paneldan boshqariladi)."""

    __tablename__ = "p2p_cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    number: Mapped[str] = mapped_column(String(32))
    holder: Mapped[str] = mapped_column(String(64), default="")
    kind: Mapped[str] = mapped_column(String(16), default="")  # Uzcard | Humo | Visa ...
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)


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
    # Jonli progress: booster /progress buyrug'i bilan yangilaydi
    progress_stars: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    winrate: Mapped[int | None] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
    reminded: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")  # 30 daqiqa oldin eslatma


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


class PaymentCard(TimestampMixin, Base):
    """Pul yechish uchun saqlangan kartalar. Raqam shifrlangan holda saqlanadi."""

    __tablename__ = "payment_cards"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    number_enc: Mapped[str] = mapped_column(Text)
    last4: Mapped[str] = mapped_column(String(4))
    brand: Mapped[str] = mapped_column(String(16))
    holder: Mapped[str] = mapped_column(String(64), default="")
    expiry: Mapped[str] = mapped_column(String(5), default="")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------- Arena: ball, vazifalar, prognoz, jamoa
class PointsEntry(TimestampMixin, Base):
    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    amount: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(32))
    idem_key: Mapped[str] = mapped_column(String(120), unique=True)


class MissionCounter(Base):
    """Vazifa progressi: (foydalanuvchi, vazifa, davr) bo'yicha hisoblagich."""

    __tablename__ = "mission_counters"
    __table_args__ = (UniqueConstraint("user_id", "key", "period", name="uq_mission_counter"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    key: Mapped[str] = mapped_column(String(32))
    period: Mapped[str] = mapped_column(String(16))
    count: Mapped[int] = mapped_column(Integer, default=0)
    claimed: Mapped[bool] = mapped_column(Boolean, default=False)


class PredictionMatch(TimestampMixin, Base):
    __tablename__ = "prediction_matches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    title: Mapped[str] = mapped_column(String(120))
    team_a: Mapped[str] = mapped_column(String(64))
    team_b: Mapped[str] = mapped_column(String(64))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="open", index=True)  # open | settled | cancelled
    result: Mapped[str | None] = mapped_column(String(1))  # a | b


class Prediction(TimestampMixin, Base):
    __tablename__ = "predictions"
    __table_args__ = (UniqueConstraint("match_id", "user_id", name="uq_prediction"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    match_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("prediction_matches.id"), index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))
    pick: Mapped[str] = mapped_column(String(1))


class TeamPost(TimestampMixin, Base):
    __tablename__ = "team_posts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(8))  # player | team
    name: Mapped[str] = mapped_column(String(64))
    lane: Mapped[str] = mapped_column(String(16), default="")
    rank: Mapped[str] = mapped_column(String(32), default="")
    online: Mapped[str] = mapped_column(String(32), default="")
    note: Mapped[str] = mapped_column(String(300), default="")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active")


# ---------------------------------------------------------------- Hamkor dasturi
class PartnerVideo(TimestampMixin, Base):
    __tablename__ = "partner_videos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), index=True)
    platform: Mapped[str] = mapped_column(String(16))
    url: Mapped[str] = mapped_column(String(300), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending | approved | rejected
    views: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    tier: Mapped[int] = mapped_column(Integer, default=0)
    reward: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str | None] = mapped_column(String(300))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
