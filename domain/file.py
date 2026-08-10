"""Models returned by the file API."""

from pydantic import BaseModel


class FileUploadResponse(BaseModel):
    fileId: int
    objectKey: str
    originalName: str
    contentType: str
    size: int
    downloadUrl: str
