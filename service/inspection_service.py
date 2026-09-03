# backend/service/inspection_service.py

import base64
import binascii
import json
import math
from io import BytesIO

from fastapi import HTTPException, status
from PIL import Image, ImageDraw, ImageOps
from client import ai_client
from domain.inspection import (
    InspectionCreateRequest,
    InspectionRequest,
    InspectionResponse,
    InspectionSaveRequest,
)
from repository import inspection_repository, model_catalog_repository
from service import ai_error_service, file_service, geocoding_service

# ==============================================================================
# 1. AI 분석 결과 데이터 가공 및 이미지 렌더링 헬퍼
# ==============================================================================


# 분석 결과 딕셔너리에서 Data-URL 형식의 라벨링 이미지 문자열 추출 (camelCase/snake_case 호환)
def _annotated_image_data(analysis: dict) -> str | None:
    for key in ("annotatedImage", "annotated_image"):
        value = analysis.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


# AI 서버의 픽셀 좌표[x1, y1, x2, y2]를 정규화 좌표[x, y, w, h]로 변환 및 유효성 검증
def _normalize_analysis(analysis: dict) -> dict:
    normalized = dict(analysis)
    image_info = analysis.get("image")
    image_width = image_info.get("width") if isinstance(image_info, dict) else None
    image_height = image_info.get("height") if isinstance(image_info, dict) else None
    detections = []

    for item in analysis.get("detections") or []:
        if not isinstance(item, dict):
            continue
        bbox = item.get("bbox")
        if not isinstance(bbox, list) or len(bbox) != 4:
            continue
        try:
            values = [float(value) for value in bbox]
        except (TypeError, ValueError):
            continue
        if not all(math.isfinite(value) for value in values):
            continue

        # 픽셀 좌표계인 경우 0~1 사이 정규화 비율 좌표로 환산
        if image_width and image_height and max(values) > 1:
            x1, y1, x2, y2 = values
            values = [
                x1 / image_width,
                y1 / image_height,
                (x2 - x1) / image_width,
                (y2 - y1) / image_height,
            ]
        x, y, width, height = values
        x, y = max(0.0, x), max(0.0, y)
        width, height = min(width, 1.0 - x), min(height, 1.0 - y)
        if width <= 0 or height <= 0:
            continue
        detections.append(
            {
                "className": str(
                    item.get("className") or item.get("class_name") or "UNKNOWN"
                ),
                "confidence": float(item.get("confidence") or 0),
                "bbox": [x, y, width, height],
            }
        )
    normalized["detections"] = detections
    return normalized


# 원본 이미지 위에 탐지 바운딩 박스 및 라벨 텍스트를 직접 그려 Data-URL로 반환
def _render_annotated_image(source_data_url: str, detections: list[dict]) -> str:
    encoded = source_data_url.split(",", 1)[-1]
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
        with Image.open(BytesIO(image_bytes)) as source:
            canvas = ImageOps.exif_transpose(source).convert("RGB")
    except (ValueError, binascii.Error, OSError) as error:
        raise HTTPException(
            status_code=422, detail="Original inspection image could not be rendered."
        ) from error

    draw = ImageDraw.Draw(canvas)
    width, height = canvas.size
    for detection in detections:
        x, y, box_width, box_height = detection["bbox"]
        left, top = round(x * width), round(y * height)
        right, bottom = round((x + box_width) * width), round((y + box_height) * height)
        label = f"{detection['className']} {detection['confidence']:.0%}"
        draw.rectangle(
            (left, top, right, bottom), outline="#ef4444", width=max(2, width // 300)
        )
        draw.text((left + 4, max(0, top - 18)), label, fill="#ef4444")

    output = BytesIO()
    canvas.save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(
        "ascii"
    )


# 탐지 결과 정규화 및 어노테이션 이미지 누락 시 자체 렌더링 보완
def _prepare_analysis(analysis: dict, source_data_url: str) -> dict:
    normalized = _normalize_analysis(analysis)
    if not _annotated_image_data(normalized):
        normalized["annotatedImage"] = _render_annotated_image(
            source_data_url, normalized["detections"]
        )
    return normalized


# 문자열 형태의 좌표("위도,경도") 유효성 검증 및 파싱
def _parse_legacy_coordinates(coordinates: str) -> tuple[float | None, float | None]:
    try:
        latitude, longitude = (
            float(value.strip()) for value in coordinates.split(",", 1)
        )
    except (AttributeError, TypeError, ValueError):
        return None, None
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return None, None
    return latitude, longitude


# ==============================================================================
# 2. 실시간 AI 추론 및 현장 점검 등록 서비스
# ==============================================================================


# AI 모델 추론 서버에 이미지 탐지 분석 요청
def analyze_image(payload: InspectionRequest) -> InspectionResponse:
    try:
        result = ai_client.detect_image(payload.image)
        return InspectionResponse.model_validate(result)
    except Exception as error:
        raise ai_error_service.to_http_exception(error) from error
    except ValueError as error:
        raise HTTPException(
            status_code=502,
            detail="AI 서버의 객체 탐지 응답 형식이 올바르지 않습니다.",
        ) from error


# 신규 점검 등록 엔트리포인트 (weather_info 지원 추가)
def create_inspection(
    payload: InspectionCreateRequest, user: dict, weather_info: dict | None = None
) -> dict:
    return _create_inspection_with_image(payload, user, weather_info=weather_info)


# 현장 점검 저장 (DRAFT 초안 상태로 등록, weather_info 지원 추가)
def save_inspection(
    payload: InspectionSaveRequest, user: dict, weather_info: dict | None = None
) -> dict:
    latitude, longitude = _parse_legacy_coordinates(payload.coordinates)
    request = InspectionCreateRequest(
        image=payload.image,
        title=payload.title,
        location=payload.location_name,
        address=payload.address,
        notes=payload.notes,
        latitude=latitude,
        longitude=longitude,
    )
    return _create_inspection_with_image(
        request, user, status="DRAFT", weather_info=weather_info
    )


# 이미지 저장, 지오코딩 좌표 보정, 점검/탐지 결과 DB 일괄 저장 처리 (weather_info 파라미터 연동)
def _create_inspection_with_image(
    payload: InspectionCreateRequest,
    user: dict,
    *,
    status: str = "REVIEW_REQUIRED",
    weather_info: dict | None = None,
) -> dict:
    analysis_unavailable = False
    try:
        analysis = ai_client.detect_image(payload.image)
    except Exception as error:
        # AI 서버 일시 장애 시에도 점검 건 저장이 실패하지 않도록 빈 결과로 처리
        analysis = {"detections": []}
        analysis_unavailable = True

    if not analysis_unavailable:
        analysis = _prepare_analysis(analysis, payload.image)

    original = file_service.store_inspection_data_image(
        payload.image, user["id"], "ORIGINAL"
    )
    annotated_data = _annotated_image_data(analysis)
    annotated = None
    if isinstance(annotated_data, str) and annotated_data:
        annotated = file_service.store_inspection_data_image(
            annotated_data, user["id"], "ANNOTATED"
        )

    latitude, longitude = payload.latitude, payload.longitude
    if latitude is None or longitude is None:
        resolved = geocoding_service.geocode(payload.location)
        if resolved:
            latitude, longitude = resolved
    location_id = inspection_repository.find_or_create_location(
        payload.location.strip(), user["id"], latitude, longitude, payload.address
    )

    # 기상청 날씨 정보 파싱 (미전달 시 기본값 방어)
    weather_desc = weather_info.get("weather", "맑음") if weather_info else "맑음"
    rainfall = float(weather_info.get("rainfall", 0.0)) if weather_info else 0.0
    weather_event = (
        weather_info.get("weather_event", "CLEAR") if weather_info else "CLEAR"
    )

    inspection_id = inspection_repository.create_inspection(
        location_id=location_id,
        user_id=user["id"],
        title=payload.title.strip(),
        notes=payload.notes,
        status="FAILED" if analysis_unavailable else status,
        weather=weather_desc,
        rainfall=rainfall,
        weather_event=weather_event,
    )
    original_image_id = inspection_repository.create_inspection_image(
        inspection_id, "ORIGINAL", original
    )
    annotated_image_id = None
    if annotated:
        annotated_image_id = inspection_repository.create_inspection_image(
            inspection_id, "ANNOTATED", annotated
        )
    if not analysis_unavailable:
        inspection_repository.save_detection_result(
            inspection_id,
            original_image_id,
            annotated_image_id,
            analysis,
        )
    return {
        "inspectionId": inspection_id,
        "message": "점검과 분석 이미지가 저장되었습니다.",
        "detections": analysis.get("detections") or [],
    }


# ==============================================================================
# 3. 점검 이력 조회, 이미지 조회, 담당자 배정 및 삭제
# ==============================================================================


# 점검 이력 목록 조회 및 JSON 파싱
def get_recent_history(user: dict, limit: int) -> list[dict]:
    rows = inspection_repository.find_inspection_history(
        limit=limit,
        user_id=user["id"],
        is_admin=user.get("role") == "ADMIN",
    )
    result = []
    for row in rows:
        detections = row.get("detections") or []
        if isinstance(detections, str):
            detections = json.loads(detections)
        result.append(
            {
                "id": row["id"],
                "title": row["title"],
                "location": row["location"],
                "address": row.get("address"),
                "coordinates": row.get("coordinates"),
                "capturedAt": row["capturedAt"],
                "status": row["status"],
                "priority": row["priority"],
                "notes": row.get("notes"),
                "aiOpinion": row.get("aiOpinion"),
                "inspectorName": row["inspectorName"],
                "wasteSummary": row["wasteSummary"],
                "detections": detections,
                "imageId": row.get("imageId"),
                "assigneeId": row.get("assigneeId"),
                "assigneeName": row.get("assigneeName"),
            }
        )
    return result


# 점검 원본/분석 이미지 파일 조회
def get_history_image(inspection_id: int, user: dict, kind: str | None = None):
    return file_service.open_inspection_image(inspection_id, user, kind)


# 점검 이력 단건 논리 삭제 (권한 검증 포함)
def delete_history(inspection_id: int, user: dict) -> None:
    inspection = inspection_repository.find_accessible_inspection(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="삭제할 수 있는 점검 이력을 찾을 수 없습니다.",
        )
    if not inspection_repository.soft_delete_inspection(inspection_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 삭제된 점검 이력입니다.",
        )


# 현장 수거/조치 배정 가능한 작업자 목록 조회
def get_assignees() -> list[dict]:
    return inspection_repository.find_active_assignees()


# 점검 건 현장 조치 담당자 배정
def assign_history(inspection_id: int, assignee_id: int, user: dict) -> dict:
    inspection = inspection_repository.find_accessible_inspection(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="점검 이력을 찾을 수 없습니다.",
        )

    assignee = inspection_repository.find_active_user(assignee_id)
    if not assignee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="일반 사용자를 제외한 활성 계정만 담당자로 지정할 수 있습니다.",
        )

    inspection_repository.assign_inspection(inspection_id, assignee_id, user["id"])
    return {"inspectionId": inspection_id, "assignee": assignee}


# 저장된 원본 이미지를 기반으로 AI 재분석 실행 및 결과 갱신
def reanalyze_inspection(inspection_id: int, user: dict) -> dict:
    inspection = inspection_repository.find_accessible_inspection(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not inspection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inspection history not found.",
        )

    stored_file, content_type = file_service.open_inspection_image(
        inspection_id, user, "ORIGINAL"
    )
    try:
        image_bytes = stored_file.read()
    finally:
        stored_file.close()
        stored_file.release_conn()

    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original inspection image not found.",
        )

    image_data_url = (
        f"data:{content_type};base64,"
        f"{base64.b64encode(image_bytes).decode('ascii')}"
    )
    try:
        analysis = ai_client.detect_image(image_data_url)
    except Exception as error:
        raise ai_error_service.to_http_exception(error) from error

    analysis = _prepare_analysis(analysis, image_data_url)
    annotated_data = _annotated_image_data(analysis)

    annotated = file_service.store_inspection_data_image(
        annotated_data, user["id"], "ANNOTATED"
    )
    original_image_id = inspection_repository.find_inspection_image_id(
        inspection_id, "ORIGINAL"
    )
    if original_image_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original inspection image metadata not found.",
        )

    # 기존 ANNOTATED 이미지 및 기존 탐지 결과 삭제/정리
    inspection_repository.clear_previous_analysis(inspection_id)

    annotated_image_id = inspection_repository.create_inspection_image(
        inspection_id, "ANNOTATED", annotated
    )
    inspection_repository.save_detection_result(
        inspection_id, original_image_id, annotated_image_id, analysis
    )
    return {
        "inspectionId": inspection_id,
        "annotatedImageId": annotated_image_id,
        "message": "Analysis image has been regenerated.",
        "detections": analysis.get("detections") or [],
    }


# ==============================================================================
# 4. 재점검(Re-inspection) 및 라벨링 관리 서비스
# ==============================================================================


# 재점검 대상(DRAFT) 점검 목록 조회
def get_reinspection_targets(user: dict) -> list[dict]:
    return inspection_repository.find_reinspection_targets(
        user["id"], user.get("role") == "ADMIN"
    )


# 재점검 건 일괄 최종 승인 및 어노테이션 이미지 최신화 (REVIEW_REQUIRED 전환)
def approve_reinspection_targets(inspection_ids: list[int], user: dict) -> dict:
    unique_ids = list(dict.fromkeys(inspection_ids))
    if not unique_ids:
        raise HTTPException(status_code=422, detail="승인할 점검을 선택해주세요.")
    pending_details = [
        get_reinspection_detail(inspection_id, user) for inspection_id in unique_ids
    ]
    inspection_repository.finalize_reinspection_annotations(unique_ids)
    affected = inspection_repository.approve_reinspection_targets(
        unique_ids, user["id"], user.get("role") == "ADMIN"
    )
    if affected != len(unique_ids):
        raise HTTPException(
            status_code=409,
            detail="점검 대기 상태가 아니거나 접근할 수 없는 항목이 포함되어 있습니다.",
        )
    for inspection_id, detail in zip(unique_ids, pending_details):
        _refresh_reinspection_annotated_image(
            inspection_id, detail.get("detections") or [], user
        )
    return {
        "selectedCount": len(unique_ids),
        "affectedCount": affected,
        "status": "REVIEW_REQUIRED",
    }


# 재점검 단건 상세 정보 조회
def get_reinspection_detail(inspection_id: int, user: dict) -> dict:
    detail = inspection_repository.find_reinspection_detail(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not detail:
        raise HTTPException(status_code=404, detail="재점검 대상을 찾을 수 없습니다.")
    return detail


# 재점검 라벨링용 활성 폐기물 분류 목록 조회
def get_reinspection_classes() -> list[dict]:
    return inspection_repository.find_active_waste_types()


# 재점검 수정된 바운딩 박스를 반영하여 ANNOTATED 이미지 재생성 및 스토리지 갱신
def _refresh_reinspection_annotated_image(
    inspection_id: int, detections: list[dict], user: dict
) -> int:
    stored_file, content_type = file_service.open_inspection_image(
        inspection_id, user, "ORIGINAL"
    )
    try:
        image_bytes = stored_file.read()
    finally:
        stored_file.close()
        stored_file.release_conn()
    if not image_bytes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Original inspection image not found.",
        )
    source_data_url = (
        f"data:{content_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    )
    rendered_detections = [
        {
            "className": detection.get("className") or "UNKNOWN",
            "confidence": float(detection.get("confidence") or 0),
            "bbox": [
                float(detection.get("bboxX") or 0),
                float(detection.get("bboxY") or 0),
                float(detection.get("bboxWidth") or 0),
                float(detection.get("bboxHeight") or 0),
            ],
        }
        for detection in detections
    ]
    annotated_data = _render_annotated_image(source_data_url, rendered_detections)
    stored = file_service.store_inspection_data_image(
        annotated_data, user["id"], "ANNOTATED"
    )
    return inspection_repository.create_inspection_image(
        inspection_id, "ANNOTATED", stored
    )


# 재점검 수동 라벨링 좌표 검증 및 저장
def save_reinspection_annotations(inspection_id: int, payload, user: dict) -> dict:
    detail = inspection_repository.find_reinspection_detail(
        inspection_id, user["id"], user.get("role") == "ADMIN"
    )
    if not detail:
        raise HTTPException(status_code=404, detail="재점검 대상을 찾을 수 없습니다.")
    for box in payload.boxes:
        x, y, width, height = box.bbox
        if (
            min(box.bbox) < 0
            or max(box.bbox) > 1
            or width <= 0
            or height <= 0
            or x + width > 1
            or y + height > 1
        ):
            raise HTTPException(
                status_code=422, detail="Bounding Box 좌표는 0~1 범위여야 합니다."
            )
    inspection_repository.save_reinspection_annotations(
        inspection_id, payload.boxes, payload.deletedIds, user["id"]
    )
    return get_reinspection_detail(inspection_id, user)


# ==============================================================================
# 5. 재점검 AI 모델 카탈로그 및 아티팩트 관리
# ==============================================================================


# AI 모델 선택 및 관리 권한 검증
def _require_reinspection_model_role(user: dict) -> None:
    if user.get("role") not in {"ADMIN", "MANAGER", "INSPECTOR"}:
        raise HTTPException(
            status_code=403, detail="You do not have permission to select a model."
        )


# 사용 가능한 AI 모델 목록 동기화 및 성능 순 정렬 반환
def get_reinspection_models(user: dict) -> dict:
    _require_reinspection_model_role(user)
    try:
        catalog = ai_client.get_ai_models()
    except Exception as error:
        raise ai_error_service.to_http_exception(error) from error
    model_catalog_repository.sync_model_catalog(catalog)
    catalog = model_catalog_repository.apply_candidate_flags(catalog)
    catalog["models"] = sorted(
        catalog.get("models", []),
        key=lambda model: (
            not bool(model.get("isCandidate")),
            -(float(model.get("map50_95") or 0)),
            -(float(model.get("map50") or 0)),
        ),
    )
    return catalog


# 특정 점검 건에 적용할 AI 모델 선택 및 활성화
def select_reinspection_model(inspection_id: int, model_id: str, user: dict) -> dict:
    _require_reinspection_model_role(user)
    get_reinspection_detail(inspection_id, user)
    selected_id = model_id.strip()
    if not selected_id:
        raise HTTPException(status_code=422, detail="A model must be selected.")
    try:
        catalog = ai_client.select_ai_model(selected_id)
    except Exception as error:
        raise ai_error_service.to_http_exception(error) from error
    model_catalog_repository.sync_model_catalog(catalog)
    return {
        "inspectionId": inspection_id,
        "selectedModelId": catalog.get("selectedModelId") or selected_id,
    }


# 재점검에 사용된 AI 모델의 상세 메타데이터 및 클래스별 평가 지표 조회
def get_reinspection_model_detail(inspection_id: int, user: dict) -> dict:
    inspection = get_reinspection_detail(inspection_id, user)
    catalog = ai_client.get_ai_models()
    model_catalog_repository.sync_model_catalog(catalog)
    model_id = inspection.get("modelExternalId")
    if not model_id:
        model_name = inspection.get("modelName")
        matched = next(
            (
                model
                for model in catalog.get("models", [])
                if model.get("id") == model_name or model.get("name") == model_name
            ),
            None,
        )
        model_id = matched.get("id") if matched else None
    if not model_id:
        raise HTTPException(
            status_code=404,
            detail="해당 재점검에 사용된 모델 상세 정보를 찾을 수 없습니다.",
        )
    try:
        detail = ai_client.get_ai_model_detail(model_id)
    except Exception as error:
        raise ai_error_service.to_http_exception(error) from error
    model_catalog_repository.sync_model_detail(detail)
    model_catalog_repository.sync_reviewed_class_metrics()
    detail["classMetrics"] = model_catalog_repository.find_model_class_metrics(model_id)
    detail["inspectionId"] = inspection_id
    detail["modelName"] = inspection.get("modelName")
    detail["modelVersion"] = inspection.get("modelVersion")
    return detail


# AI 모델 관련 아티팩트 파일(가중치/시각화 이미지 등) 데이터 반환
def get_reinspection_model_artifact(inspection_id: int, artifact: str, user: dict):
    inspection = get_reinspection_detail(inspection_id, user)
    model_id = inspection.get("modelExternalId")
    if not model_id or not artifact.startswith(f"{model_id}/"):
        raise HTTPException(status_code=404, detail="모델 산출물을 찾을 수 없습니다.")
    try:
        return ai_client.get_ai_artifact(artifact)
    except Exception as error:
        raise ai_error_service.to_http_exception(error) from error
