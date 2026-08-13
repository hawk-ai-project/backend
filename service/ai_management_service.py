import math

from fastapi import HTTPException

from repository import ai_management_repository as repository


def _validate_bbox(bbox):
    if bbox is None:
        return
    x, y, width, height = bbox
    if min(bbox) < 0 or max(bbox) > 1 or width <= 0 or height <= 0 or x + width > 1 or y + height > 1:
        raise HTTPException(422, "Bounding box values must be normalized between 0 and 1.")


def list_detections(page, page_size, keyword, result, review_status, class_name, min_confidence):
    items, total = repository.find_detections(
        page, page_size, keyword, result, review_status, class_name, min_confidence,
    )
    return {"items": items, "page": page, "pageSize": page_size, "totalItems": total,
            "totalPages": math.ceil(total / page_size) if total else 0}


def review_detection(detection_id, payload, admin_id):
    _validate_bbox(payload.bbox)
    if not repository.find_detection(detection_id):
        raise HTTPException(404, "Detection not found.")
    actual_type_id = repository.find_or_create_waste_type(payload.actualClass) if payload.actualClass else None
    repository.update_review(detection_id, payload, admin_id, actual_type_id)
    return repository.find_detection(detection_id)


def create_missed(payload, admin_id):
    _validate_bbox(payload.bbox)
    actual_type_id = repository.find_or_create_waste_type(payload.actualClass)
    detection_id = repository.create_missed_detection(
        payload.inspectionId, actual_type_id, payload.bbox, payload.errorReason,
        payload.retrainingCandidate, admin_id,
    )
    if not detection_id:
        raise HTTPException(404, "A successful detection run was not found for this inspection.")
    return repository.find_detection(detection_id)


def get_statistics():
    return repository.statistics()


def get_classes():
    return repository.find_waste_types()
