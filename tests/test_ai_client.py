import json
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum

import httpx
import pytest
from pydantic import BaseModel

from client import ai_client


def transport_json(status: int, payload):
    return httpx.MockTransport(
        lambda request: httpx.Response(status, json=payload, request=request)
    )


def test_chat_uses_answer_and_forwards_intent():
    result = ai_client.generate_chat(
        "safe context",
        "question",
        transport=transport_json(200, {"answer": "answer", "intent": "FAQ"}),
    )
    assert result == {"answer": "answer", "intent": "FAQ", "action": None}


def test_chat_falls_back_to_message():
    result = ai_client.generate_chat(
        "", "question", transport=transport_json(200, {"message": "fallback"})
    )
    assert result["answer"] == "fallback"


def test_chat_accepts_safe_navigation_action():
    result = ai_client.generate_chat(
        "",
        "question",
        transport=transport_json(
            200,
            {
                "answer": "go",
                "intent": "NAVIGATION",
                "action": {"type": "NAVIGATE", "path": "/histories"},
            },
        ),
    )
    assert result["action"] == {"type": "NAVIGATE", "path": "/histories"}


@pytest.mark.parametrize(
    "action",
    [
        {"type": "OPEN_URL", "path": "/histories"},
        {"type": "NAVIGATE", "path": "https://example.com"},
        {"type": "NAVIGATE", "path": "javascript:alert(1)"},
        {"type": "NAVIGATE", "path": "/admin"},
    ],
)
def test_chat_drops_unsafe_action_without_failing_answer(action):
    result = ai_client.generate_chat(
        "",
        "question",
        transport=transport_json(200, {"answer": "safe", "action": action}),
    )
    assert result["answer"] == "safe"
    assert result["action"] is None


def test_chat_rejects_missing_answer_and_message():
    with pytest.raises(ai_client.AIResponseError):
        ai_client.generate_chat("", "question", transport=transport_json(200, {}))


@pytest.mark.parametrize("context_type,inspection,reinspection", [
    ("GLOBAL", None, None),
    ("INSPECTION", {"inspectionId": 3}, None),
    ("REINSPECTION", None, {"inspectionId": 3, "reviewSummary": {}}),
])
def test_model_recommendations_request_contract(context_type, inspection, reinspection):
    context = {
        "contextType": context_type,
        "candidateModels": [{"modelId": "model-a"}],
        "gpu": [{"name": "GPU"}],
        "inspection": inspection,
        "reinspection": reinspection,
    }
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"recommendations": [], "warnings": []}, request=request)

    result = ai_client.generate_model_recommendations(context, transport=httpx.MockTransport(handler))
    assert captured == {"path": "/api/ai/model-recommendations", "body": context}
    assert result == {"recommendations": [], "warnings": []}


def test_model_recommendations_serializes_database_native_context_values():
    class ReviewStatus(str, Enum):
        REVIEWED = "REVIEWED"

    class ContextMetadata(BaseModel):
        source: str

    context = {
        "contextType": "GLOBAL",
        "candidateModels": [{
            "modelId": "model-a",
            "precision": Decimal("0.9123"),
            "recall": Decimal("0.8765"),
            "map50": Decimal("0.9501"),
            "map50_95": Decimal("0.7012"),
        }],
        "gpu": [],
        "inspection": {
            "createdAt": datetime(2026, 8, 25, 12, 30, tzinfo=timezone.utc),
            "inspectionDate": date(2026, 8, 25),
            "reviewStatus": ReviewStatus.REVIEWED,
            "metadata": ContextMetadata(source="database"),
        },
        "reinspection": None,
    }
    captured = {}

    def handler(request):
        captured["path"] = request.url.path
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"recommendations": [], "warnings": []}, request=request)

    ai_client.generate_model_recommendations(context, transport=httpx.MockTransport(handler))

    assert captured["path"] == "/api/ai/model-recommendations"
    candidate = captured["body"]["candidateModels"][0]
    assert candidate["precision"] == pytest.approx(0.9123)
    assert candidate["recall"] == pytest.approx(0.8765)
    assert candidate["map50"] == pytest.approx(0.9501)
    assert candidate["map50_95"] == pytest.approx(0.7012)
    assert captured["body"]["inspection"] == {
        "createdAt": "2026-08-25T12:30:00+00:00",
        "inspectionDate": "2026-08-25",
        "reviewStatus": "REVIEWED",
        "metadata": {"source": "database"},
    }


@pytest.mark.parametrize("payload", [{}, {"recommendations": "invalid"}, {"recommendations": [], "warnings": "invalid"}])
def test_model_recommendations_rejects_invalid_shape(payload):
    with pytest.raises(ai_client.AIResponseError):
        ai_client.generate_model_recommendations({}, transport=transport_json(200, payload))


def test_model_recommendations_rejects_malformed_json():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"not-json", request=request))
    with pytest.raises(ai_client.AIResponseError):
        ai_client.generate_model_recommendations({}, transport=transport)


@pytest.mark.parametrize("exception,expected", [
    (httpx.ConnectError("failed"), ai_client.AIConnectionError),
    (httpx.ReadTimeout("timed out"), ai_client.AITimeoutError),
])
def test_model_recommendations_maps_transport_errors(exception, expected):
    def fail(request):
        exception.request = request
        raise exception

    with pytest.raises(expected):
        ai_client.generate_model_recommendations({}, transport=httpx.MockTransport(fail))


def test_invalid_json_maps_to_bad_gateway_error():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"not-json", request=request)
    )
    with pytest.raises(ai_client.AIResponseError) as caught:
        ai_client.generate_chat("", "question", transport=transport)
    assert caught.value.status_code == 502


def test_connection_failure_maps_to_503():
    def fail(request):
        raise httpx.ConnectError("private detail", request=request)

    with pytest.raises(ai_client.AIConnectionError) as caught:
        ai_client.generate_chat("", "question", transport=httpx.MockTransport(fail))
    assert caught.value.status_code == 503
    assert "private detail" not in str(caught.value)


def test_timeout_maps_to_504():
    def fail(request):
        raise httpx.ReadTimeout("private detail", request=request)

    with pytest.raises(ai_client.AITimeoutError) as caught:
        ai_client.generate_chat("", "question", transport=httpx.MockTransport(fail))
    assert caught.value.status_code == 504


@pytest.mark.parametrize("status, expected", [(400, 502), (500, 502), (503, 503)])
def test_upstream_http_errors_are_safely_mapped(status, expected):
    with pytest.raises(ai_client.AIServerError) as caught:
        ai_client.generate_chat(
            "",
            "question",
            transport=transport_json(status, {"detail": "sensitive upstream detail"}),
        )
    assert caught.value.status_code == expected
    assert "sensitive upstream detail" not in str(caught.value)


def test_board_request_contract_and_response_validation():
    captured = {}

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"title": " title ", "summary": " summary ", "content": " content "},
            request=request,
        )

    result = ai_client.generate_board(
        {
            "location": "beach",
            "wasteSummary": "bottle 1",
            "priority": "high",
            "category": None,
            "notes": None,
        },
        transport=httpx.MockTransport(handler),
    )
    assert captured["waste_summary"] == "bottle 1"
    assert "wasteSummary" not in captured
    assert result == {"title": "title", "summary": "summary", "content": "content"}


def test_board_rejects_missing_required_field():
    with pytest.raises(ai_client.AIResponseError) as caught:
        ai_client.generate_board(
            {"location": "beach", "wasteSummary": "bottle"},
            transport=transport_json(200, {"title": "t", "summary": "s"}),
        )
    assert caught.value.status_code == 502
