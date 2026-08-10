"""Authenticated upload, download, and deletion endpoints."""

from fastapi import APIRouter, Depends, File, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from controller.auth_controller import current_auth
from domain.file import FileUploadResponse
from service import file_service


router = APIRouter(prefix="/api/files", tags=["files"])


@router.post("", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
def upload_file(file: UploadFile = File(...), auth=Depends(current_auth)):
    try:
        return file_service.upload(file, auth[0]["id"])
    finally:
        file.file.close()


@router.get("/{object_key:path}")
def download_file(object_key: str, auth=Depends(current_auth)):
    stored_file = file_service.open_download(object_key, auth[0]["id"])

    def stream():
        try:
            yield from stored_file.stream(32 * 1024)
        finally:
            stored_file.close()
            stored_file.release_conn()

    content_type = stored_file.headers.get("Content-Type", "application/octet-stream")
    return StreamingResponse(stream(), media_type=content_type)


@router.delete("/{object_key:path}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(object_key: str, auth=Depends(current_auth)):
    file_service.delete(object_key, auth[0]["id"])
    return Response(status_code=status.HTTP_204_NO_CONTENT)

