from datetime import datetime
from typing import Optional
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
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="client", index=True
    )  # superadmin | advisor | client
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    advisor_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    advisor: Mapped[Optional["User"]] = relationship("User", remote_side=[id], backref="clients")


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


def run_lightweight_migrations():
    """Agrega columnas nuevas de forma compatible con SQLite y PostgreSQL."""
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


run_lightweight_migrations()