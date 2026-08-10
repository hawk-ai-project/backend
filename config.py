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
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    max_upload_size_bytes: int


def get_settings() -> Settings:
    expire_minutes = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    max_upload_size = os.getenv("MAX_UPLOAD_SIZE_MB", "20")
    try:
        parsed_expire_minutes = int(expire_minutes)
        parsed_max_upload_size = int(max_upload_size) * 1024 * 1024
    except ValueError as exc:
        raise RuntimeError("Numeric environment variables must be integers") from exc

    if parsed_max_upload_size <= 0:
        raise RuntimeError("MAX_UPLOAD_SIZE_MB must be greater than zero")

    return Settings(
        database_url=_required("DATABASE_URL"),
        secret_key=_required("SECRET_KEY"),
        algorithm=os.getenv("ALGORITHM", "HS256"),
        access_token_expire_minutes=parsed_expire_minutes,
        minio_endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        minio_access_key=os.getenv("MINIO_ACCESS_KEY", "hawk-backend"),
        minio_secret_key=os.getenv(
            "MINIO_SECRET_KEY", "change-this-to-another-long-random-password"
        ),
        minio_bucket=os.getenv("MINIO_BUCKET", "hawk-files"),
        minio_secure=os.getenv("MINIO_SECURE", "false").lower() in {"1", "true", "yes"},
        max_upload_size_bytes=parsed_max_upload_size,
    )


settings = get_settings()
