from datetime import datetime
from typing import Any, Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    Float,
    Boolean,
    String,
    JSON,
    DateTime,
    Text,
    ForeignKey,
    UniqueConstraint,
    inspect,
    text,
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Mapped, mapped_column
from app.core.config import DATABASE_URL

is_sqlite = DATABASE_URL.startswith("sqlite")
engine_kwargs = (
    {"connect_args": {"check_same_thread": False}}
    if is_sqlite
    else {"pool_pre_ping": True}
)

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(20), nullable=False, default="local")  # local | google | github | managed
    oauth_sub: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="client", index=True)  # superadmin | advisor | client
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    advisor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    advisor: Mapped[Optional["User"]] = relationship("User", remote_side=[id], foreign_keys=[advisor_id])


class CompanyData(Base):
    __tablename__ = "company_data"

    ticker = Column(String, primary_key=True, index=True)
    cik = Column(String, index=True)
    raw_facts = Column(JSON)
    last_updated = Column(DateTime, default=datetime.utcnow)


class CompanyProfile(Base):
    __tablename__ = "company_profiles"
    ticker = Column(String, primary_key=True, index=True)
    name = Column(String)
    website = Column(String)
    description = Column(Text)


class CompanyMarketCache(Base):
    __tablename__ = "company_market_cache"
    ticker = Column(String, primary_key=True, index=True)
    market_data = Column(JSON)
    last_updated = Column(DateTime, default=datetime.utcnow)


class CompanyEstimatesCache(Base):
    __tablename__ = "company_estimates_cache"
    ticker = Column(String, primary_key=True, index=True)
    estimates_data = Column(JSON)
    last_updated = Column(DateTime, default=datetime.utcnow)


class CompanyOwnershipCache(Base):
    __tablename__ = "company_ownership_cache"
    ticker = Column(String, primary_key=True, index=True)
    ownership_data = Column(JSON)
    last_updated = Column(DateTime, default=datetime.utcnow)


class CompanySegmentsCache(Base):
    __tablename__ = "company_segments_cache"
    ticker = Column(String, primary_key=True, index=True)
    business_segments = Column(JSON, default=list)
    geo_segments = Column(JSON, default=list)
    key_clients_notes = Column(Text, nullable=True)
    is_custom = Column(Boolean, default=False, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow)


class PriceHistoryCache(Base):
    __tablename__ = "price_history_cache"
    cache_key = Column(String, primary_key=True, index=True)  # Ej: "MSFT:1y"
    ticker = Column(String, index=True)
    range_key = Column(String)
    payload = Column(JSON)
    last_updated = Column(DateTime, default=datetime.utcnow)


class MacroSeriesCache(Base):
    __tablename__ = "macro_series_cache"
    cache_key = Column(String, primary_key=True, index=True)
    payload = Column(JSON)
    last_updated = Column(DateTime, default=datetime.utcnow)


class IndexValuationSnapshot(Base):
    __tablename__ = "index_valuation_snapshots"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    snapshot_date = Column(String(10), nullable=False, index=True)  # YYYY-MM-DD
    index_code = Column(String(20), nullable=False, index=True)    # SP500, NDX, DJI, RUT, EWZ, EEM
    proxy_ticker = Column(String(15), nullable=False)
    price = Column(Float, nullable=True)
    pe_trailing = Column(Float, nullable=True)
    pe_forward = Column(Float, nullable=True)
    earnings_yield_pct = Column(Float, nullable=True)
    dividend_yield_pct = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("snapshot_date", "index_code", name="uq_index_daily_snapshot"),
    )


class Watchlist(Base):
    __tablename__ = "watchlists"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(60), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    watchlist_id = Column(Integer, ForeignKey("watchlists.id", ondelete="CASCADE"), nullable=False, index=True)
    ticker = Column(String(20), nullable=False, index=True)
    position = Column(Integer, default=0, nullable=False)
    buy_target_price = Column(Float, nullable=True)
    sell_target_price = Column(Float, nullable=True)
    thesis_note = Column(Text, nullable=True)
    alerts = Column(JSON, default=list)
    added_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("watchlist_id", "ticker", name="uq_watchlist_ticker"),
    )


class AlertNotification(Base):
    __tablename__ = "alert_notifications"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    rule_fingerprint = Column(String(120), nullable=False, index=True)
    watchlist_id = Column(Integer, nullable=False, index=True)
    watchlist_name = Column(String(60), nullable=False)
    ticker = Column(String(20), nullable=False, index=True)
    company_name = Column(String(120), nullable=False)
    alert_type = Column(String(30), nullable=False)  # buy_target | sell_target | custom_metric
    title = Column(String(120), nullable=False)
    detail = Column(String(255), nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    triggered_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ClientProfile(Base):
    __tablename__ = "client_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    risk_profile: Mapped[str] = mapped_column(
        String(30), nullable=False, default="moderado"
    )  # conservador | moderado | agresivo
    investment_horizon: Mapped[str] = mapped_column(
        String(30), nullable=False, default="largo_plazo"
    )  # corto_plazo | mediano_plazo | largo_plazo
    target_currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    tx_type: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # BUY | SELL | DIVIDEND | DEPOSIT | WITHDRAWAL
    ticker: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, index=True)
    tx_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    unit_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    commission: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


def run_lightweight_migrations():
    """Agrega columnas nuevas y ajusta nulabilidad de forma compatible con SQLite y PostgreSQL."""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)

    with engine.begin() as conn:
        if inspector.has_table("watchlist_items"):
            wi_cols = {c["name"] for c in inspector.get_columns("watchlist_items")}
            if "position" not in wi_cols:
                conn.execute(
                    text(
                        "ALTER TABLE watchlist_items ADD COLUMN position INTEGER NOT NULL DEFAULT 0"
                    )
                )

        if inspector.has_table("watchlists"):
            wl_cols = {c["name"] for c in inspector.get_columns("watchlists")}
            if "user_id" not in wl_cols:
                conn.execute(
                    text("ALTER TABLE watchlists ADD COLUMN user_id INTEGER NULL")
                )

        if not is_sqlite and inspector.has_table("users"):
            user_cols = {c["name"]: c for c in inspector.get_columns("users")}
            hp_col = user_cols.get("hashed_password")
            if hp_col and hp_col.get("nullable") is False:
                conn.execute(
                    text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL")
                )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ArgentinaSocialOverride(Base):
    __tablename__ = "argentina_social_overrides"

    series_id: Mapped[str] = mapped_column(String(64), primary_key=True, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(160), nullable=False)
    points_json: Mapped[Any] = mapped_column(JSON, nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


def run_schema_migrations() -> None:
    """Agrega columnas nuevas a tablas existentes de forma idempotente (SQLite/PostgreSQL)."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing_cols = {col["name"] for col in inspector.get_columns("users")}

    with engine.begin() as conn:
        if "username" not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(50)"))
        if "auth_provider" not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN auth_provider VARCHAR(20) DEFAULT 'local' NOT NULL"))
        if "oauth_sub" not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN oauth_sub VARCHAR(255)"))
        if "email_verified" not in existing_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT TRUE NOT NULL"))

        # Poblar username en filas previas que no lo tengan
        rows = conn.execute(text("SELECT id, email, username FROM users")).fetchall()
        used_usernames = {
            (r[2] or "").strip().lower()
            for r in rows
            if r[2] and str(r[2]).strip()
        }
        for uid, email, uname in rows:
            if not uname or not str(uname).strip():
                base = (email or f"user{uid}").split("@")[0].lower()
                base = "".join(ch for ch in base if ch.isalnum() or ch in ("_", "."))[:30] or f"user{uid}"
                candidate = base
                idx = 1
                while candidate in used_usernames:
                    idx += 1
                    candidate = f"{base}{idx}"
                used_usernames.add(candidate)
                conn.execute(
                    text("UPDATE users SET username = :u WHERE id = :id"),
                    {"u": candidate, "id": uid},
                )

        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)"))


run_lightweight_migrations()