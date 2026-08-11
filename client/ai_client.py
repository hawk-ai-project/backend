"""Synchronous client for the remote GPU inference server."""

import base64
import binascii
from typing import Any

import httpx

from config import settings


class AIServerError(RuntimeError):
    """Raised when the GPU server is unavailable or returns an invalid response."""


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        with httpx.Client(trust_env=False) as client:
            response = client.post(
                f"{settings.ai_server_url}{path}",
                json=payload,
                timeout=settings.ai_server_timeout_seconds,
            )
        response.raise_for_status()
    except httpx.TimeoutException as error:
        raise AIServerError("AI 서버 응답 시간이 초과되었습니다.") from error
    except httpx.ConnectError as error:
        raise AIServerError("AI 서버에 연결할 수 없습니다.") from error
    except httpx.HTTPStatusError as error:
        detail = error.response.text[:500]
        raise AIServerError(
            f"AI 서버가 오류를 반환했습니다 ({error.response.status_code}): {detail}"
        ) from error
    except httpx.HTTPError as error:
        raise AIServerError(f"AI 서버 통신 중 오류가 발생했습니다: {error}") from error

    try:
        data = response.json()
    except ValueError as error:
        raise AIServerError("AI 서버 응답이 JSON 형식이 아닙니다.") from error
    if not isinstance(data, dict):
        raise AIServerError("AI 서버 응답은 JSON 객체여야 합니다.")
    return data


def generate_chat(context: str, message: str) -> str:
    data = _post("/api/ai/chat", {"context": context, "message": message})
    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise AIServerError("AI 서버의 챗봇 응답에 answer가 없습니다.")
    return answer.strip()


def generate_board(payload: dict[str, Any]) -> dict[str, Any]:
    data = _post(
        "/api/ai/board",
        {
            "location": payload["location"],
            "waste_summary": payload["wasteSummary"],
            "priority": payload.get("priority"),
            "category": payload.get("category"),
            "notes": payload.get("notes"),
        },
    )
    draft = data.get("draft", data)
    if not isinstance(draft, dict):
        raise AIServerError("AI 서버의 게시글 응답 형식이 올바르지 않습니다.")
    return draft


def detect_image(image: str) -> dict[str, Any]:
    encoded = image
    content_type = "image/jpeg"
    if image.startswith("data:"):
        try:
            header, encoded = image.split(",", 1)
            content_type = header[5:].split(";", 1)[0] or content_type
        except ValueError as error:
            raise AIServerError("이미지 data URL 형식이 올바르지 않습니다.") from error
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise AIServerError("이미지가 올바른 base64 형식이 아닙니다.") from error
    if not image_bytes:
        raise AIServerError("빈 이미지는 분석할 수 없습니다.")

    extension = content_type.rsplit("/", 1)[-1].replace("jpeg", "jpg")
    try:
        with httpx.Client(trust_env=False) as client:
            response = client.post(
                f"{settings.ai_server_url}/api/ai/detect",
                files={"file": (f"inspection.{extension}", image_bytes, content_type)},
                timeout=settings.ai_server_timeout_seconds,
            )
        response.raise_for_status()
    except httpx.TimeoutException as error:
        raise AIServerError("AI 서버 응답 시간이 초과되었습니다.") from error
    except httpx.ConnectError as error:
        raise AIServerError("AI 서버에 연결할 수 없습니다.") from error
    except httpx.HTTPStatusError as error:
        detail = error.response.text[:500]
        raise AIServerError(
            f"AI 서버가 오류를 반환했습니다 ({error.response.status_code}): {detail}"
        ) from error
    except httpx.HTTPError as error:
        raise AIServerError(f"AI 서버 통신 중 오류가 발생했습니다: {error}") from error

    try:
        data = response.json()
    except ValueError as error:
        raise AIServerError("AI 서버 응답이 JSON 형식이 아닙니다.") from error
    if not isinstance(data, dict):
        raise AIServerError("AI 서버 응답은 JSON 객체여야 합니다.")
    return data
