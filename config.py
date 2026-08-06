"""Application settings loaded from the local .env file."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    algorithm: str
    access_token_expire_minutes: int


def get_settings() -> Settings:
    expire_minutes = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    try:
        parsed_expire_minutes = int(expire_minutes)
    except ValueError as exc:
        raise RuntimeError(
            "ACCESS_TOKEN_EXPIRE_MINUTES must be an integer"
        ) from exc

    return Settings(
        database_url=_required("DATABASE_URL"),
        secret_key=_required("SECRET_KEY"),
        algorithm=os.getenv("ALGORITHM", "HS256"),
        access_token_expire_minutes=parsed_expire_minutes,
    )


settings = get_settings()
