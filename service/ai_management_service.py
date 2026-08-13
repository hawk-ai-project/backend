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


def browse_data(page,page_size,keyword,class_name,tag_ids,result,review_status,retraining):
    items,total=repository.find_data_items(page,page_size,keyword,class_name,tag_ids,result,review_status,retraining)
    return {"items":items,"page":page,"pageSize":page_size,"totalItems":total,
            "totalPages":math.ceil(total/page_size) if total else 0}


def get_tags():
    return repository.list_data_tags()


def create_tag(payload,admin_id):
    tag_id=repository.create_data_tag(payload.name,payload.categoryCode,payload.description,admin_id)
    if not tag_id:
        raise HTTPException(404,"Tag category not found.")
    return next((tag for tag in repository.list_data_tags() if tag["id"]==tag_id),{"id":tag_id})


def bulk_action(payload,admin_id):
    unique_ids=list(dict.fromkeys(payload.inspectionIds))
    affected=repository.bulk_data_action(unique_ids,payload.action,payload.tagIds,admin_id)
    return {"message":"Bulk action completed.","selectedCount":len(unique_ids),"affectedCount":affected}


def get_data_detail(inspection_id):
    detail=repository.find_data_detail(inspection_id)
    if not detail:
        raise HTTPException(404,"Data item not found.")
    return detail


def delete_annotation(detection_id):
    if not repository.delete_detection(detection_id):
        raise HTTPException(404,"Annotation not found.")
