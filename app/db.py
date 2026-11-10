from collections.abc import Iterator

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool: ConnectionPool | None = None


def init_pool(database_url: str) -> None:
    global _pool
    if _pool is not None:
        return
    _pool = ConnectionPool(
        conninfo=database_url,
        min_size=1,
        max_size=10,
        timeout=5,
        kwargs={"autocommit": True, "row_factory": dict_row},
        open=True,
    )


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def get_conn() -> Iterator[object]:
    if _pool is None:
        raise RuntimeError("Database pool is not initialised")
    with _pool.connection() as conn:
        yield conn
