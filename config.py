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
    refresh_cookie_secure: bool
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    max_upload_size_bytes: int
    ai_server_url: str
    ai_server_connect_timeout: float
    ai_server_read_timeout: float


def get_settings() -> Settings:
    max_upload_size = os.getenv("MAX_UPLOAD_SIZE_MB", "20")
    ai_connect_timeout = os.getenv("AI_SERVER_CONNECT_TIMEOUT", "5")
    ai_read_timeout = os.getenv(
        "AI_SERVER_READ_TIMEOUT",
        os.getenv("AI_SERVER_TIMEOUT_SECONDS", "120"),
    )
    try:
        parsed_max_upload_size = int(max_upload_size) * 1024 * 1024
        parsed_ai_connect_timeout = float(ai_connect_timeout)
        parsed_ai_read_timeout = float(ai_read_timeout)
    except ValueError as exc:
        raise RuntimeError("Numeric environment variables must be valid numbers") from exc

    if parsed_max_upload_size <= 0:
        raise RuntimeError("MAX_UPLOAD_SIZE_MB must be greater than zero")
    if parsed_ai_connect_timeout <= 0 or parsed_ai_read_timeout <= 0:
        raise RuntimeError("AI server timeouts must be greater than zero")

    return Settings(
        database_url=_required("DATABASE_URL"),
        secret_key=_required("SECRET_KEY"),
        algorithm=os.getenv("ALGORITHM", "HS256"),
        refresh_cookie_secure=os.getenv("REFRESH_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "hawk-backend"),
        minio_secret_key=os.getenv(
            "MINIO_SECRET_KEY", "change-this-to-another-long-random-password"
        ),
        minio_bucket=os.getenv("MINIO_BUCKET", "hawk-files"),
        minio_secure=os.getenv("MINIO_SECURE", "false").lower() in {"1", "true", "yes"},
        max_upload_size_bytes=parsed_max_upload_size,
        ai_server_url=_required("AI_SERVER_URL").rstrip("/"),
        ai_server_connect_timeout=parsed_ai_connect_timeout,
        ai_server_read_timeout=parsed_ai_read_timeout,
    )


settings = get_settings()
