import json
import re
from typing import Any

from fastapi import HTTPException

from client import ai_client
from domain.model_recommendation import ModelRecommendationRequest, RecommendationContextType
from repository import model_recommendation_repository as repository
from service import ai_error_service


def _warnings(models: list[dict[str, Any]], context_data: dict[str, Any] | None, gpu: list[dict[str, Any]]) -> list[str]:
    warnings = []
    if any(model.get("map50_95") is None or model.get("recall") is None for model in models):
        warnings.append("일부 후보 모델의 성능 데이터가 누락되어 있습니다.")
    if context_data is not None and not context_data.get("detections"):
        warnings.append("검사 탐지 데이터가 없어 제한된 정보로 추천했습니다.")
    if not gpu:
        warnings.append("GPU 상태 데이터가 없어 실행 자원 적합성을 확인하지 못했습니다.")
    return warnings


def _context(payload: ModelRecommendationRequest, user: dict) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    models = repository.find_candidate_models()
    if not models:
        raise HTTPException(status_code=400, detail="추천 가능한 후보 모델이 없습니다.")
    inspection = None
    reinspection = None
    if payload.contextType == RecommendationContextType.INSPECTION:
        inspection = repository.find_inspection_context(
            payload.inspectionId, user["id"], user.get("role") == "ADMIN"
        )
        if inspection is None:
            raise HTTPException(status_code=404, detail="검사 정보를 찾을 수 없습니다.")
    elif payload.contextType == RecommendationContextType.REINSPECTION:
        reinspection = repository.find_reinspection_context(
            payload.inspectionId, user["id"], user.get("role") == "ADMIN"
        )
        if reinspection is None:
            raise HTTPException(status_code=404, detail="검사 정보를 찾을 수 없습니다.")
    gpu = repository.find_gpu_status()
    context = {
        "contextType": payload.contextType.value,
        "candidateModels": models,
        "gpu": gpu,
        "inspection": inspection,
        "reinspection": reinspection,
    }
    return context, models, _warnings(models, inspection or reinspection, gpu)


def _score(payload: ModelRecommendationRequest, model: dict[str, Any], context: dict[str, Any]) -> tuple:
    if payload.contextType == RecommendationContextType.REINSPECTION:
        summary = (context.get("reinspection") or {}).get("reviewSummary") or {}
        fn_classes = set(summary.get("falseNegativeClasses") or [])
        fp_classes = set(summary.get("falsePositiveClasses") or [])
        metrics = {item.get("className"): item for item in model.get("classMetrics") or []}
        recalls = [float(metrics[name].get("recall") or -1) for name in fn_classes if name in metrics]
        precisions = [float(metrics[name].get("precision") or -1) for name in fp_classes if name in metrics]
        recall_score = sum(recalls) / len(recalls) if recalls else -1
        precision_score = sum(precisions) / len(precisions) if precisions else -1
        if int(summary.get("falseNegative") or 0) >= int(summary.get("falsePositive") or 0):
            return (recall_score, precision_score, float(model.get("map50_95") or -1))
        return (precision_score, recall_score, float(model.get("map50_95") or -1))
    return tuple(float(model.get(key) or -1) for key in ("map50_95", "recall", "precision", "map50"))


def _fallback_items(payload: ModelRecommendationRequest, models: list[dict[str, Any]], context: dict[str, Any]) -> list[dict]:
    ranked = sorted(models, key=lambda model: _score(payload, model, context), reverse=True)[:3]
    items = []
    for rank, model in enumerate(ranked, 1):
        strengths = []
        if model.get("map50_95") is not None:
            strengths.append(f"mAP50-95 지표가 {model['map50_95']}입니다.")
        if payload.contextType == RecommendationContextType.REINSPECTION:
            summary = (context.get("reinspection") or {}).get("reviewSummary") or {}
            focus = "Recall" if int(summary.get("falseNegative") or 0) >= int(summary.get("falsePositive") or 0) else "Precision"
            strengths.append(f"재점검 문제 클래스의 {focus} 지표를 우선 비교했습니다.")
        items.append({
            "rank": rank,
            "modelId": model["modelId"],
            "modelName": model["name"],
            "label": f"지표 기반 {rank}순위",
            "summary": "검증 가능한 성능 지표를 기준으로 선정했습니다.",
            "strengths": strengths,
            "bestFor": [],
            "tradeoffs": [],
            "reasons": strengths.copy(),
        })
    return items


def _fallback(
    payload: ModelRecommendationRequest,
    models: list[dict[str, Any]],
    warnings: list[str],
    current: str | None,
    context: dict[str, Any],
) -> dict:
    recommendations = _fallback_items(payload, models, context)
    selected = recommendations[0]
    return {
        "contextType": payload.contextType.value,
        "recommendedModelId": selected["modelId"],
        "recommendedModelName": selected["modelName"],
        "currentModelId": current,
        "confidence": 0.5,
        "summary": selected["summary"],
        "reasons": selected["reasons"],
        "warnings": [*warnings, "LLM 응답을 검증할 수 없어 지표 기반 fallback을 사용했습니다."],
        "candidateCount": len(models),
        "recommendations": recommendations,
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


def _text_list(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError("recommendation text fields must be string lists")
    return [item.strip() for item in value]


def _validated_recommendations(result: dict[str, Any], models: list[dict[str, Any]]) -> list[dict]:
    raw_items = result.get("recommendations")
    if not isinstance(raw_items, list) or len(raw_items) != min(3, len(models)):
        raise ValueError("recommendations must contain the expected candidate count")
    by_id = {model["modelId"]: model for model in models}
    seen = set()
    validated = []
    for expected_rank, item in enumerate(raw_items, 1):
        if not isinstance(item, dict) or item.get("rank") != expected_rank:
            raise ValueError("recommendation ranks must be consecutive")
        model_id = item.get("modelId")
        if model_id not in by_id or model_id in seen:
            raise ValueError("recommendation model must be a unique candidate")
        label, summary = item.get("label"), item.get("summary")
        if not isinstance(label, str) or not label.strip() or not isinstance(summary, str) or not summary.strip():
            raise ValueError("recommendation label and summary are required")
        seen.add(model_id)
        validated.append({
            "rank": expected_rank,
            "modelId": model_id,
            "modelName": by_id[model_id]["name"],
            "label": label.strip(),
            "summary": summary.strip(),
            "strengths": _text_list(item.get("strengths")),
            "bestFor": _text_list(item.get("bestFor")),
            "tradeoffs": _text_list(item.get("tradeoffs")),
            "reasons": _text_list(item.get("reasons", [])),
        })
    return validated


def recommend(payload: ModelRecommendationRequest, user: dict) -> dict:
    if payload.contextType == RecommendationContextType.GLOBAL and user.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    context, models, warnings = _context(payload, user)
    current = (context.get("inspection") or context.get("reinspection") or {}).get("currentModelId")
    purposes = {
        RecommendationContextType.GLOBAL: "후보 중 전체 운영 환경 기준으로 추천하세요.",
        RecommendationContextType.INSPECTION: "현재 이미지와 탐지 특성에 적합한 후보를 추천하세요.",
        RecommendationContextType.REINSPECTION: "재점검에서 확인된 오탐, 미탐, class 수정을 줄이는 후보를 추천하세요.",
    }
    prompt = purposes[payload.contextType] + " " + (
        "다음 JSON context만 사용해 candidateModels 중 최대 3개를 순위화하세요. 후보가 3개 미만이면 존재하는 후보만 반환하세요. "
        "모든 modelId는 candidateModels의 modelId와 정확히 일치해야 하며 중복할 수 없습니다. DB에 없는 모델, metric, GPU 요구량을 만들지 말고 "
        "각 모델의 근거 있는 특징을 구분해 설명하세요. 자동 모델 변경은 수행하지 않습니다. JSON 객체만 반환하세요. "
        "필드: recommendations(rank, modelId, label, summary, strengths, bestFor, tradeoffs, reasons), confidence(0~1, 선택), warnings(문자열 배열)."
    )
    try:
        generated = ai_client.generate_chat(json.dumps(context, ensure_ascii=False, default=str), prompt)
    except ai_client.AIServerError as error:
        raise ai_error_service.to_http_exception(error) from error
    try:
        result = _parse_answer(generated["answer"])
        recommendations = _validated_recommendations(result, models)
        chosen = recommendations[0]
        confidence = float(result.get("confidence", 0.5))
        if not 0 <= confidence <= 1:
            raise ValueError("invalid recommendation confidence")
        llm_warnings = _text_list(result.get("warnings", []))
        reasons = chosen["reasons"] or chosen["strengths"]
        return {
            "contextType": payload.contextType.value,
            "recommendedModelId": chosen["modelId"],
            "recommendedModelName": chosen["modelName"],
            "currentModelId": current,
            "confidence": confidence,
            "summary": chosen["summary"],
            "reasons": reasons,
            "warnings": [*warnings, *llm_warnings],
            "candidateCount": len(models),
            "recommendations": recommendations,
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return _fallback(payload, models, warnings, current, context)
