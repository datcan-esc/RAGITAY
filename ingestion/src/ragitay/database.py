from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"

DEFAULT_DB_SETTINGS = {
    "host": "localhost",
    "port": "5433",
    "dbname": "ragitay",
    "user": "ragitay",
    "password": "ragitay",
}


def load_env_file(path: Path = DEFAULT_ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        os.environ.setdefault(key, value)


def build_postgres_conninfo() -> str:
    load_env_file()

    database_url = os.getenv("DATABASE_URL", "").strip()
    if database_url:
        return database_url

    settings = {
        "host": os.getenv("POSTGRES_HOST", DEFAULT_DB_SETTINGS["host"]),
        "port": os.getenv("POSTGRES_PORT", DEFAULT_DB_SETTINGS["port"]),
        "dbname": os.getenv("POSTGRES_DB", DEFAULT_DB_SETTINGS["dbname"]),
        "user": os.getenv("POSTGRES_USER", DEFAULT_DB_SETTINGS["user"]),
        "password": os.getenv("POSTGRES_PASSWORD", DEFAULT_DB_SETTINGS["password"]),
    }

    return " ".join(f"{key}={value}" for key, value in settings.items())
