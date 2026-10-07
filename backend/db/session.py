from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from backend.db.config import get_database_url


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or get_database_url())
