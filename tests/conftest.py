import os
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import ClientCursor

ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL = os.environ.get("ADMIN_DATABASE_URL", "")

if not ADMIN_URL:
    raise RuntimeError(
        "Set ADMIN_DATABASE_URL to a Postgres URL whose database name ends with _test."
    )

_db_name = urlparse(ADMIN_URL).path.lstrip("/").split("?", 1)[0]
if not _db_name.endswith("_test"):
    raise RuntimeError(
        f"Refusing to run tests against database {_db_name!r}. The name must end with _test."
    )

os.environ["DATABASE_URL"] = ADMIN_URL
os.environ["API_KEY"] = "test-key"
os.environ["APP_ENV"] = "test"
os.environ["APP_VERSION"] = "test"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["TZ_NAME"] = "Asia/Kolkata"


def _apply(path: Path) -> None:
    script = path.read_text()
    with psycopg.connect(ADMIN_URL, autocommit=True, cursor_factory=ClientCursor) as conn:
        conn.execute(script)


@pytest.fixture(scope="session")
def database_url() -> str:
    _apply(ROOT / "sql" / "001_schema.sql")
    _apply(ROOT / "sql" / "002_seed.sql")
    return ADMIN_URL


@pytest.fixture
def reset_db(database_url: str) -> Iterator[None]:
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE TABLE bookings RESTART IDENTITY")
        conn.execute("UPDATE seats SET status = 'available'")
    yield


@pytest.fixture(scope="session")
def client(database_url: str) -> Iterator[TestClient]:
    from app.config import get_settings

    get_settings.cache_clear()
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
