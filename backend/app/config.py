from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class Settings:
    app_name: str = "RAGITAY Backend"
    app_version: str = "0.1.0"
    database_url: str = ""
    postgres_host: str = "localhost"
    postgres_port: str = "5433"
    postgres_db: str = "ragitay"
    postgres_user: str = "ragitay"
    postgres_password: str = "ragitay"
    embedding_model_name: str = "intfloat/multilingual-e5-base"
    embedding_device: str = ""
    embedding_local_files_only: bool = True
    cors_allow_origins: tuple[str, ...] = ("*",)
    cors_allow_credentials: bool = False


def load_env_file(path: Path = DEFAULT_ENV_PATH) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'").strip('"'))


def _as_bool(value: str, default: bool) -> bool:
    if not value:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_env_file()

    raw_origins = os.getenv("BACKEND_CORS_ALLOW_ORIGINS", "*").strip()
    origins = tuple(part.strip() for part in raw_origins.split(",") if part.strip()) or ("*",)

    return Settings(
        database_url=os.getenv("DATABASE_URL", "").strip(),
        postgres_host=os.getenv("POSTGRES_HOST", "localhost").strip(),
        postgres_port=os.getenv("POSTGRES_PORT", "5433").strip(),
        postgres_db=os.getenv("POSTGRES_DB", "ragitay").strip(),
        postgres_user=os.getenv("POSTGRES_USER", "ragitay").strip(),
        postgres_password=os.getenv("POSTGRES_PASSWORD", "ragitay").strip(),
        embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "intfloat/multilingual-e5-base").strip(),
        embedding_device=os.getenv("EMBEDDING_DEVICE", "").strip(),
        embedding_local_files_only=_as_bool(os.getenv("EMBEDDING_LOCAL_FILES_ONLY", "true"), True),
        cors_allow_origins=origins,
        cors_allow_credentials=_as_bool(os.getenv("BACKEND_CORS_ALLOW_CREDENTIALS", "false"), False),
    )
