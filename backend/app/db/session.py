from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings


def _sqlite_url(path: str) -> str:
    if path.startswith("sqlite:"):
        return path
    return f"sqlite:///{path}"


engine = create_engine(_sqlite_url(settings.db_path), connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
