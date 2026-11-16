from sqlalchemy import create_engine, Column, String, JSON, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from app.core.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

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

class PriceHistoryCache(Base):
    __tablename__ = "price_history_cache"
    cache_key = Column(String, primary_key=True, index=True)  # Ej: "MSFT:1y"
    ticker = Column(String, index=True)
    range_key = Column(String)
    payload = Column(JSON)
    last_updated = Column(DateTime, default=datetime.utcnow)

# Inicializar la base de datos (crea las tablas nuevas si no existen)
Base.metadata.create_all(bind=engine)