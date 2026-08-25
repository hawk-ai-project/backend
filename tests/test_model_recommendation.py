import json
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from client import ai_client
from domain.model_recommendation import ModelRecommendationRequest
from service import model_recommendation_service as service


MODELS = [
    {"modelId": "train/s", "name": "YOLO-S", "map50_95": .60, "recall": .70, "precision": .80, "map50": .90, "classMetrics": []},
    {"modelId": "train/m", "name": "YOLO-M", "map50_95": .75, "recall": .85, "precision": .82, "map50": .92, "classMetrics": []},
]
ADMIN = {"id": 1, "role": "ADMIN"}
USER = {"id": 2, "role": "USER"}


def payload(context="GLOBAL", inspection_id=None):
    return ModelRecommendationRequest(contextType=context, inspectionId=inspection_id)


def mock_context(inspection=None, models=MODELS):
    return patch.multiple(
        service.repository,
        find_candidate_models=lambda: models,
        find_gpu_status=lambda: [{"name": "GPU"}],
        find_inspection_context=lambda *_: inspection,
    )


def ai_result(model_id="train/m"):
    return {"answer": json.dumps({
        "recommendedModelId": model_id, "confidence": .87, "summary": "best",
        "reasons": ["higher recall"], "warnings": [],
    })}


def test_global_recommendation_success():
    with mock_context(), patch.object(service.ai_client, "generate_chat", return_value=ai_result()):
        result = service.recommend(payload(), ADMIN)
    assert result["recommendedModelId"] == "train/m"
    assert result["candidateCount"] == 2


def test_global_without_candidates_is_400():
    with mock_context(models=[]), pytest.raises(HTTPException) as error:
        service.recommend(payload(), ADMIN)
    assert error.value.status_code == 400


def test_inspection_requires_id():
    with pytest.raises(ValidationError):
        payload("INSPECTION")


def test_global_rejects_inspection_id():
    with pytest.raises(ValidationError):
        payload("GLOBAL", 1)


def test_missing_inspection_is_404():
    with mock_context(None), pytest.raises(HTTPException) as error:
        service.recommend(payload("INSPECTION", 404), USER)
    assert error.value.status_code == 404


@pytest.mark.parametrize("context_type", ["INSPECTION", "REINSPECTION"])
def test_inspection_context_recommendation(context_type):
    inspection = {"inspectionId": 3, "currentModelId": "train/s", "detections": [{"className": "foam"}]}
    with mock_context(inspection), patch.object(service.ai_client, "generate_chat", return_value=ai_result()):
        result = service.recommend(payload(context_type, 3), USER)
    assert result["currentModelId"] == "train/s"
    assert result["contextType"] == context_type


@pytest.mark.parametrize("answer", ["not json", json.dumps({"recommendedModelId": "invented"})])
def test_invalid_llm_response_uses_candidate_fallback(answer):
    with mock_context(), patch.object(service.ai_client, "generate_chat", return_value={"answer": answer}):
        result = service.recommend(payload(), ADMIN)
    assert result["recommendedModelId"] == "train/m"
    assert "fallback" in result["warnings"][-1]


def test_ai_server_unavailable_maps_to_503():
    with mock_context(), patch.object(service.ai_client, "generate_chat", side_effect=ai_client.AIConnectionError()):
        with pytest.raises(HTTPException) as error:
            service.recommend(payload(), ADMIN)
    assert error.value.status_code == 503


def test_global_requires_admin():
    with pytest.raises(HTTPException) as error:
        service.recommend(payload(), USER)
    assert error.value.status_code == 403


def test_missing_data_adds_warnings():
    incomplete = [{"modelId": "train/s", "name": "S", "map50_95": None, "recall": None}]
    with mock_context(models=incomplete), patch.object(service.ai_client, "generate_chat", return_value=ai_result("train/s")):
        result = service.recommend(payload(), ADMIN)
    assert any("누락" in warning for warning in result["warnings"])


def test_recommendation_does_not_select_model():
    with mock_context(), patch.object(service.ai_client, "generate_chat", return_value=ai_result()), \
            patch.object(service.ai_client, "select_ai_model") as select:
        service.recommend(payload(), ADMIN)
    select.assert_not_called()
