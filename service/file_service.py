"""Private MinIO object storage operations."""

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from minio import Minio
from minio.error import S3Error

from config import settings
from repository import file_repository


_client: Minio | None = None


def get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _client


def _file_size(file: UploadFile) -> int:
    current = file.file.tell()
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(current)
    return size


def _object_key(user_id: int, filename: str | None) -> str:
    # Only retain a short extension. The original filename never becomes a path.
    suffix = Path(filename or "").suffix.lower()
    if len(suffix) > 16 or not suffix.replace(".", "").isalnum():
        suffix = ""
    today = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    return f"users/{user_id}/{today}/{uuid4().hex}{suffix}"


def _owned_file(object_key: str, user_id: int) -> dict:
    stored = file_repository.find_owned_active(object_key, user_id)
    if stored is None:
        raise HTTPException(status_code=404, detail="File not found.")
    return stored


def upload(file: UploadFile, user_id: int) -> dict:
    if not file.filename:
        raise HTTPException(status_code=422, detail="A filename is required.")

    size = _file_size(file)
    if size <= 0:
        raise HTTPException(status_code=422, detail="Empty files cannot be uploaded.")
    if size > settings.max_upload_size_bytes:
        limit_mb = settings.max_upload_size_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File size exceeds {limit_mb} MB.")

    object_key = _object_key(user_id, file.filename)
    content_type = file.content_type or "application/octet-stream"
    file.file.seek(0)
    try:
        result = get_client().put_object(
            settings.minio_bucket,
            object_key,
            file.file,
            length=size,
            content_type=content_type,
        )
    except S3Error as exc:
        raise HTTPException(status_code=502, detail="File storage upload failed.") from exc

    try:
        file_id = file_repository.create(
            uploaded_by=user_id,
            bucket_name=settings.minio_bucket,
            object_key=object_key,
            original_name=file.filename,
            mime_type=content_type,
            byte_size=size,
            etag=result.etag,
        )
    except Exception as exc:
        # Avoid an orphan object if saving its metadata fails.
        try:
            get_client().remove_object(settings.minio_bucket, object_key)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail="File metadata could not be saved.") from exc

    encoded_key = quote(object_key, safe="/")
    return {
        "fileId": file_id,
        "objectKey": object_key,
        "originalName": file.filename,
        "contentType": content_type,
        "size": size,
        "downloadUrl": f"/api/files/{encoded_key}",
    }


def open_download(object_key: str, user_id: int):
    stored = _owned_file(object_key, user_id)
    try:
        return get_client().get_object(stored["bucket_name"], object_key)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject"}:
            raise HTTPException(status_code=404, detail="File not found.") from exc
        raise HTTPException(status_code=502, detail="File storage download failed.") from exc


def delete(object_key: str, user_id: int) -> None:
    stored = _owned_file(object_key, user_id)
    try:
        get_client().stat_object(stored["bucket_name"], object_key)
        get_client().remove_object(stored["bucket_name"], object_key)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject"}:
            raise HTTPException(status_code=404, detail="File not found.") from exc
        raise HTTPException(status_code=502, detail="File storage delete failed.") from exc
    if not file_repository.soft_delete(stored["id"], user_id):
        raise HTTPException(status_code=409, detail="File metadata was already deleted.")
