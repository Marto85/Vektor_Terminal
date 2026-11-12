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

# Inicializar la base de datos (crea el archivo SQLite físico)
Base.metadata.create_all(bind=engine)