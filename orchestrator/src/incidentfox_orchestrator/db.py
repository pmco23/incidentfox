from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def init_engine(db_url: str) -> None:
    global _engine, _SessionLocal
    connect_args = {}
    if (db_url or "").strip().lower().startswith("sqlite"):
        # Enable sqlite usage for local tests/dev; FastAPI TestClient uses threads.
        connect_args = {"check_same_thread": False}
    _engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
    _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("DB engine not initialized (call init_engine on startup)")
    return _engine


@contextmanager
def db_session() -> Generator[Session, None, None]:
    global _SessionLocal
    if _SessionLocal is None:
        raise RuntimeError(
            "DB session factory not initialized (call init_engine on startup)"
        )
    s: Session = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
