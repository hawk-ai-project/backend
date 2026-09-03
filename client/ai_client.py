"""HTTP client for the remote GPU AI server.

Only request metadata is logged. User messages, database context, model paths,
credentials, and upstream response bodies are deliberately excluded.
"""

import base64
import binascii
import logging
from time import perf_counter
from typing import Any
from uuid import uuid4

import httpx
from fastapi.encoders import jsonable_encoder

from config import settings


logger = logging.getLogger(__name__)
ALLOWED_NAVIGATION_PATHS = {
    "/inspection",
    "/histories",
    "/analytics",
    "/boards",
    "/boards/write",
    "/login",
}


class AIServerError(RuntimeError):
    status_code = 502
    public_message = "AI 서버 응답을 처리할 수 없습니다."

    def __init__(self, message: str | None = None):
        super().__init__(message or self.public_message)


class AIConnectionError(AIServerError):
    status_code = 503
    public_message = "AI 서버에 연결할 수 없습니다."


class AITimeoutError(AIServerError):
    status_code = 504
    public_message = "AI 서버 응답 시간이 초과되었습니다."


class AIResponseError(AIServerError):
    status_code = 502
    public_message = "AI 서버가 올바르지 않은 응답을 반환했습니다."


class AIUnavailableError(AIServerError):
    status_code = 503
    public_message = "AI 서버를 현재 사용할 수 없습니다."


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=settings.ai_server_connect_timeout,
        read=settings.ai_server_read_timeout,
        write=settings.ai_server_read_timeout,
        pool=settings.ai_server_connect_timeout,
    )


def _log_result(request_id: str, endpoint: str, status: int | str, started: float) -> None:
    logger.info(
        "AI request id=%s endpoint=%s status=%s elapsed_ms=%d",
        request_id,
        endpoint,
        status,
        round((perf_counter() - started) * 1000),
    )


def _raise_for_status(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as error:
        if error.response.status_code == 503:
            raise AIUnavailableError() from error
        raise AIResponseError() from error


def _decode_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError as error:
        raise AIResponseError("AI 서버 응답이 JSON 형식이 아닙니다.") from error
    if not isinstance(data, dict):
        raise AIResponseError("AI 서버 응답은 JSON 객체여야 합니다.")
    return data


def _post_json(
    endpoint: str,
    payload: dict[str, Any],
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    request_id = uuid4().hex
    started = perf_counter()
    status: int | str = "network_error"
    try:
        with httpx.Client(trust_env=False, timeout=_timeout(), transport=transport) as client:
            response = client.post(f"{settings.ai_server_url}{endpoint}", json=payload)
        status = response.status_code
        _raise_for_status(response)
        return _decode_json(response)
    except httpx.TimeoutException as error:
        status = "timeout"
        raise AITimeoutError() from error
    except httpx.ConnectError as error:
        raise AIConnectionError() from error
    except httpx.HTTPError as error:
        raise AIConnectionError("AI 서버 통신에 실패했습니다.") from error
    finally:
        _log_result(request_id, endpoint, status, started)


def _get_json(
    endpoint: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    request_id = uuid4().hex
    started = perf_counter()
    status: int | str = "network_error"
    try:
        with httpx.Client(trust_env=False, timeout=_timeout(), transport=transport) as client:
            response = client.get(f"{settings.ai_server_url}{endpoint}")
        status = response.status_code
        _raise_for_status(response)
        return _decode_json(response)
    except httpx.TimeoutException as error:
        status = "timeout"
        raise AITimeoutError() from error
    except httpx.ConnectError as error:
        raise AIConnectionError() from error
    except httpx.HTTPError as error:
        raise AIConnectionError("AI 서버 통신에 실패했습니다.") from error
    finally:
        _log_result(request_id, endpoint, status, started)


def _sanitize_remote_action(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    action_type = value.get("type")
    path = value.get("path")

    # 허용된 Navigation Action만 통과
    if action_type != "NAVIGATE" or path not in ALLOWED_NAVIGATION_PATHS:
        return None
    return {"type": "NAVIGATE", "path": path}


def generate_chat(
    context: str,
    message: str,
    *,
    history: list[dict[str, str]] | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    # 서버가 답변을 생성할 때 현재 Context와 대화 흐름을 함께 참조한다.
    data = _post_json(
        "/api/ai/chat",
        {"context": context, "message": message, "history": history or []},
        transport=transport,
    )
    answer = data.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        answer = data.get("message")
    if not isinstance(answer, str) or not answer.strip():
        raise AIResponseError("AI 서버의 챗봇 응답에 answer 또는 message가 없습니다.")
    intent = data.get("intent")
    return {
        "answer": answer.strip(),
        "intent": intent if isinstance(intent, str) and intent.strip() else None,
        "action": _sanitize_remote_action(data.get("action")),
    }


def generate_model_recommendations(
    context: dict[str, Any],
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    data = _post_json(
        "/api/ai/model-recommendations",
        jsonable_encoder(context),
        transport=transport,
    )
    if not isinstance(data.get("recommendations"), list):
        raise AIResponseError("AI 서버의 모델 추천 응답에 recommendations 배열이 없습니다.")
    if "warnings" in data and not isinstance(data["warnings"], list):
        raise AIResponseError("AI 서버의 모델 추천 warnings는 배열이어야 합니다.")
    return data


def generate_board(
    payload: dict[str, Any],
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, str]:
    # 프런트 DTO를 AI 서버의 요청 필드에 맞춰 전달한다.
    data = _post_json(
        "/api/ai/board",
        {
            "location": payload["location"],
            "waste_summary": payload["wasteSummary"],
            "priority": payload.get("priority"),
            "category": payload.get("category"),
            "notes": payload.get("notes"),
        },
        transport=transport,
    )
    draft = data.get("draft", data)
    if not isinstance(draft, dict):
        raise AIResponseError("AI 서버의 게시글 응답은 JSON 객체여야 합니다.")

    # AI 게시글 응답의 필수 필드 검증
    result: dict[str, str] = {}
    for key in ("title", "summary", "content"):
        value = draft.get(key)
        if not isinstance(value, str) or not value.strip():
            raise AIResponseError(f"AI 서버의 게시글 응답에 {key} 필드가 없습니다.")
        result[key] = value.strip()
    return result


def detect_image(
    image: str,
    *,
    transport: httpx.BaseTransport | None = None,
) -> dict[str, Any]:
    encoded = image
    content_type = "image/jpeg"
    if image.startswith("data:"):
        try:
            header, encoded = image.split(",", 1)
            content_type = header[5:].split(";", 1)[0] or content_type
        except ValueError as error:
            raise AIResponseError("이미지 data URL 형식이 올바르지 않습니다.") from error
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as error:
        raise AIResponseError("이미지가 올바른 base64 형식이 아닙니다.") from error
    if not image_bytes:
        raise AIResponseError("빈 이미지는 분석할 수 없습니다.")

    endpoint = "/api/ai/detect"
    request_id = uuid4().hex
    started = perf_counter()
    status: int | str = "network_error"
    extension = content_type.rsplit("/", 1)[-1].replace("jpeg", "jpg")
    try:
        with httpx.Client(trust_env=False, timeout=_timeout(), transport=transport) as client:
            response = client.post(
                f"{settings.ai_server_url}{endpoint}",
                files={"file": (f"inspection.{extension}", image_bytes, content_type)},
            )
        status = response.status_code
        _raise_for_status(response)
        return _decode_json(response)
    except httpx.TimeoutException as error:
        status = "timeout"
        raise AITimeoutError() from error
    except httpx.ConnectError as error:
        raise AIConnectionError() from error
    except httpx.HTTPError as error:
        raise AIConnectionError("AI 서버 통신에 실패했습니다.") from error
    finally:
        _log_result(request_id, endpoint, status, started)


def get_ai_models(*, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    return _get_json("/api/ai/admin/models", transport=transport)


def get_ai_model_detail(model_id: str, *, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    return _get_json(f"/api/ai/admin/models/{model_id}", transport=transport)


def select_ai_model(model_id: str, *, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    return _post_json(f"/api/ai/admin/models/{model_id}/select", {}, transport=transport)


def get_ai_system(*, transport: httpx.BaseTransport | None = None) -> dict[str, Any]:
    return _get_json("/api/ai/admin/system", transport=transport)


def get_ai_artifact(relative_path: str, *, transport: httpx.BaseTransport | None = None) -> tuple[bytes, str]:
    with httpx.Client(trust_env=False, timeout=_timeout(), transport=transport) as client:
        response = client.get(f"{settings.ai_server_url}/api/ai/admin/artifacts/{relative_path}")
    _raise_for_status(response)
    return response.content, response.headers.get("content-type", "application/octet-stream")
