from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row

from backend.app.config import get_settings


def build_conninfo() -> str:
    settings = get_settings()
    if settings.database_url:
        return settings.database_url

    return " ".join(
        [
            f"host={settings.postgres_host}",
            f"port={settings.postgres_port}",
            f"dbname={settings.postgres_db}",
            f"user={settings.postgres_user}",
            f"password={settings.postgres_password}",
        ]
    )


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(build_conninfo(), row_factory=dict_row)
    register_vector(conn)
    try:
        yield conn
    finally:
        conn.close()
