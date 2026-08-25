import json
import re
from typing import Any

from fastapi import HTTPException

from client import ai_client
from domain.model_recommendation import ModelRecommendationRequest, RecommendationContextType
from repository import model_recommendation_repository as repository
from service import ai_error_service


def _warnings(models: list[dict[str, Any]], inspection: dict[str, Any] | None, gpu: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if any(model.get("map50_95") is None or model.get("recall") is None for model in models):
        warnings.append("일부 후보 모델의 성능 데이터가 누락되어 있습니다.")
    if inspection is not None and not inspection.get("detections"):
        warnings.append("검사 탐지 데이터가 없어 제한된 정보로 추천했습니다.")
    if not gpu:
        warnings.append("GPU 상태 데이터가 없어 실행 자원 적합성을 확인하지 못했습니다.")
    return warnings


def _context(payload: ModelRecommendationRequest, user: dict) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    models = repository.find_candidate_models()
    if not models:
        raise HTTPException(status_code=400, detail="추천 가능한 후보 모델이 없습니다.")
    inspection = None
    if payload.contextType != RecommendationContextType.GLOBAL:
        inspection = repository.find_inspection_context(
            payload.inspectionId, user["id"], user.get("role") == "ADMIN"
        )
        if inspection is None:
            raise HTTPException(status_code=404, detail="검사 정보를 찾을 수 없습니다.")
    gpu = repository.find_gpu_status()
    context = {
        "contextType": payload.contextType.value,
        "candidateModels": models,
        "gpu": gpu,
        "inspection": inspection,
    }
    return context, models, _warnings(models, inspection, gpu)


def _fallback(payload: ModelRecommendationRequest, models: list[dict[str, Any]], warnings: list[str], current: str | None) -> dict:
    def score(model):
        return tuple(float(model.get(key) or -1) for key in ("map50_95", "recall", "precision", "map50"))
    selected = max(models, key=score)
    return {
        "contextType": payload.contextType.value,
        "recommendedModelId": selected["modelId"],
        "recommendedModelName": selected["name"],
        "currentModelId": current,
        "confidence": 0.5,
        "summary": "검증 가능한 성능 지표를 기준으로 후보 모델을 추천했습니다.",
        "reasons": ["후보 모델 중 mAP50-95, recall, precision 순으로 비교했습니다."],
        "warnings": [*warnings, "LLM 응답을 검증할 수 없어 지표 기반 fallback을 사용했습니다."],
        "candidateCount": len(models),
    }


def _parse_answer(answer: str) -> dict[str, Any]:
    text = answer.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("recommendation must be an object")
    return value


def recommend(payload: ModelRecommendationRequest, user: dict) -> dict:
    if payload.contextType == RecommendationContextType.GLOBAL and user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    context, models, warnings = _context(payload, user)
    current = (context.get("inspection") or {}).get("currentModelId")
    prompt = (
        "다음 JSON context만 사용해 후보 모델 하나를 추천하세요. candidateModels 밖의 모델이나 수치를 만들지 마세요. "
        "자동 모델 변경은 수행하지 않습니다. JSON 객체만 반환하세요. 필드: recommendedModelId, "
        "confidence(0~1), summary, reasons(문자열 배열), warnings(문자열 배열)."
    )
    try:
        generated = ai_client.generate_chat(json.dumps(context, ensure_ascii=False, default=str), prompt)
    except ai_client.AIServerError as error:
        raise ai_error_service.to_http_exception(error) from error
    try:
        result = _parse_answer(generated["answer"])
        by_id = {model["modelId"]: model for model in models}
        chosen = by_id[result["recommendedModelId"]]
        confidence = float(result["confidence"])
        summary = result["summary"]
        reasons = result["reasons"]
        llm_warnings = result.get("warnings", [])
        if not isinstance(summary, str) or not summary.strip():
            raise ValueError("invalid recommendation summary")
        if not 0 <= confidence <= 1 or not isinstance(reasons, list) or not reasons or not isinstance(llm_warnings, list):
            raise ValueError("invalid recommendation fields")
        if not all(isinstance(item, str) and item.strip() for item in [*reasons, *llm_warnings]):
            raise ValueError("invalid recommendation text")
        return {
            "contextType": payload.contextType.value,
            "recommendedModelId": chosen["modelId"],
            "recommendedModelName": chosen["name"],
            "currentModelId": current,
            "confidence": confidence,
            "summary": summary.strip(),
            "reasons": reasons,
            "warnings": [*warnings, *llm_warnings],
            "candidateCount": len(models),
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return _fallback(payload, models, warnings, current)
