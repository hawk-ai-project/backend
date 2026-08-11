"""Translate internal AI client failures into stable public HTTP errors."""

from fastapi import HTTPException

from client.ai_client import AIServerError


def to_http_exception(error: AIServerError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail=str(error))
