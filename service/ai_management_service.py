import math

from fastapi import HTTPException

from client import ai_client
from repository import ai_management_repository as repository
from repository import model_catalog_repository


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


def get_models():
    catalog = ai_client.get_ai_models()
    model_catalog_repository.sync_model_catalog(catalog)
    model_catalog_repository.sync_reviewed_class_metrics()
    return model_catalog_repository.apply_candidate_flags(catalog)


def get_model_detail(model_id: str):
    model_catalog_repository.sync_model_catalog(ai_client.get_ai_models())
    detail = ai_client.get_ai_model_detail(model_id)
    model_catalog_repository.sync_model_detail(detail)
    model_catalog_repository.sync_reviewed_class_metrics()
    detail["classMetrics"] = model_catalog_repository.find_model_class_metrics(model_id)
    return detail


def select_model(model_id: str):
    if not model_id.strip():
        raise HTTPException(422, "Model ID is required.")
    catalog = ai_client.select_ai_model(model_id)
    model_catalog_repository.sync_model_catalog(catalog)
    model_catalog_repository.sync_reviewed_class_metrics()
    return model_catalog_repository.apply_candidate_flags(catalog)



def set_model_candidates(model_ids: list[str], candidate: bool):
    unique_ids = [model_id.strip() for model_id in dict.fromkeys(model_ids) if model_id.strip()]
    if not unique_ids:
        raise HTTPException(422, "At least one model ID is required.")
    affected = model_catalog_repository.set_model_candidates(unique_ids, candidate)
    if affected != len(unique_ids):
        raise HTTPException(404, "One or more models were not found.")
    return get_models()

def set_model_candidate(model_id: str, candidate: bool):
    if not model_id.strip():
        raise HTTPException(422, "Model ID is required.")
    if not model_catalog_repository.set_model_candidate(model_id, candidate):
        raise HTTPException(404, "Model not found.")
    return get_models()

def get_system():
    system = ai_client.get_ai_system()
    model_catalog_repository.sync_gpu_status(system)
    return system


def get_artifact(artifact: str):
    return ai_client.get_ai_artifact(artifact)


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
