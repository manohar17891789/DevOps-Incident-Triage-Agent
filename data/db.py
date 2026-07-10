"""Shared SQLAlchemy engine/session, pointed at DATABASE_URL (sqlite locally, postgres in Docker)."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)
