"""
Shared pytest configuration.

Sets the environment variables required by config.py BEFORE any test module
imports the application, and registers the Hypothesis profiles.
"""
import os
from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient
from hypothesis import settings

# Test-only environment. Assigned (not setdefault) so tests never reach a
# developer's real database or data directory.
os.environ["BACKEND_NODE_ENV"] = "test"
os.environ["DATA_DIR"] = str(Path(__file__).resolve().parents[2] / "data")
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["CORS_ORIGINS"] = "http://localhost:3000"
# Pure Python reader: runs everywhere. Tests of the mdbtools reader build it explicitly.
os.environ["ACCESS_READER"] = "access-parser"

settings.register_profile("dev", max_examples=100, deadline=None)
settings.register_profile("ci", max_examples=500, deadline=5000)


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    """Test client with a fresh in-memory database.

    The tables are created here (production runs `alembic upgrade head`
    before startup; test_migrations.py checks both give the same schema).
    Entering the client runs the application lifespan, which seeds the
    predefined rules, exactly like a real startup.
    """
    from main import app
    from models.base import Base, engine

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as client:
        yield client
    Base.metadata.drop_all(bind=engine)
