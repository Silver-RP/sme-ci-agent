import threading

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from backend.db.config import get_database_url, get_max_overflow, get_pool_size


def make_engine(url: str | None = None) -> Engine:
    return create_engine(
        url or get_database_url(), pool_size=get_pool_size(), max_overflow=get_max_overflow(), pool_pre_ping=True
    )


_engines: dict[str, Engine] = {}
_lock = threading.Lock()


def get_shared_engine(url: str | None = None) -> Engine:
    """One engine (one pool) per URL for the whole process (H-37): runs borrow connections from it."""
    key = url or get_database_url()
    with _lock:
        engine = _engines.get(key)
        if engine is None:
            engine = _engines[key] = make_engine(key)
        return engine


def dispose_shared_engines() -> None:
    """Close every pooled connection (app shutdown). Engines stay usable: they reconnect on demand."""
    with _lock:
        for engine in _engines.values():
            engine.dispose()
