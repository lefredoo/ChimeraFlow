"""
SQLAlchemy base configuration
"""
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from config import get_database_url

# Database URL from environment (fails fast if missing, AGENTS.md §7)
DATABASE_URL = get_database_url()


def _build_engine(url: str) -> Engine:
    """Create the engine, with the SQLite specifics needed for local runs and tests.

    SQLite does not enforce foreign keys unless asked to, so the pragma is set
    on every connection: it makes SQLite behave like PostgreSQL on that point.
    An in-memory SQLite database lives in a single connection, which must then
    be shared across threads (FastAPI runs sync dependencies in a thread pool).

    Args:
        url: SQLAlchemy database URL.

    Returns:
        Configured engine.
    """
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return create_engine(url, echo=False, pool_pre_ping=True)

    options: dict[str, Any] = {"echo": False}
    if parsed.database in (None, "", ":memory:"):
        options["poolclass"] = StaticPool
        options["connect_args"] = {"check_same_thread": False}
    sqlite_engine = create_engine(url, **options)

    @event.listens_for(sqlite_engine, "connect")
    def _enable_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return sqlite_engine


engine = _build_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Dependency for FastAPI routes to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
