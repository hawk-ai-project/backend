"""Read-only queries used to build model recommendation contexts."""

from typing import Any

from common.db import fetch_query


def find_candidate_models() -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT id,external_id AS modelId,name,base_model AS baseModel,
        has_weights AS hasWeights,image_size AS imageSize,batch_size AS batch,
        epochs,optimizer,is_selected AS isSelected,precision_score AS `precision`,
        recall_score AS recall,map50,map50_95 AS map50_95
        FROM ai_models WHERE is_candidate=TRUE
        ORDER BY is_selected DESC,map50_95 DESC,map50 DESC,id"""
    ) or []
    models = rows if isinstance(rows, list) else []
    if not models:
        return []
    ids = [model["id"] for model in models]
    placeholders = ",".join(["%s"] * len(ids))
    metrics = fetch_query(
        f"""SELECT model_id,class_name AS className,accuracy,
        precision_score AS `precision`,recall_score AS recall,map50,map50_95 AS map50_95,
        true_positives AS truePositives,false_positives AS falsePositives,
        false_negatives AS falseNegatives,support
        FROM ai_model_class_metrics WHERE model_id IN ({placeholders})
        ORDER BY model_id,class_name""", tuple(ids),
    ) or []
    by_model: dict[int, list[dict[str, Any]]] = {}
    for metric in metrics:
        by_model.setdefault(metric.pop("model_id"), []).append(metric)
    for model in models:
        model["classMetrics"] = by_model.get(model.pop("id"), [])
    return models


def find_gpu_status() -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT device_name AS name,memory_total_mib AS vramTotalMiB,
        memory_used_mib AS vramUsedMiB,utilization_percent AS utilizationPercent,
        temperature_c AS temperatureC,power_draw_w AS powerDrawW
        FROM ai_gpu_devices ORDER BY last_synced_at DESC,device_index LIMIT 8"""
    ) or []
    return rows if isinstance(rows, list) else []


def find_inspection_context(inspection_id: int, user_id: int, is_admin: bool) -> dict[str, Any] | None:
    permission = "" if is_admin else "AND i.inspector_id=%s"
    params = (inspection_id,) if is_admin else (inspection_id, user_id)
    row = fetch_query(
        f"""SELECT i.id AS inspectionId,img.original_name AS imageName,img.mime_type AS mimeType,
        img.byte_size AS byteSize,img.width AS imageWidth,img.height AS imageHeight,
        r.id AS runId,r.model_name AS modelName,
        r.model_version AS modelVersion,am.external_id AS currentModelId
        FROM inspections i
        LEFT JOIN inspection_images img ON img.id=(SELECT ii.id FROM inspection_images ii
          WHERE ii.inspection_id=i.id AND ii.kind='ORIGINAL' ORDER BY ii.id DESC LIMIT 1)
        LEFT JOIN detection_runs r ON r.id=(SELECT rr.id FROM detection_runs rr
          WHERE rr.inspection_id=i.id AND rr.status='SUCCEEDED' ORDER BY rr.id DESC LIMIT 1)
        LEFT JOIN ai_models am ON (am.external_id=r.model_name OR am.name=r.model_name OR am.name=r.model_version)
        WHERE i.id=%s AND i.deleted_at IS NULL {permission} LIMIT 1""", params, one=True,
    )
    if not isinstance(row, dict):
        return None
    detections = fetch_query(
        """SELECT d.id,wt.name_ko AS className,d.confidence,
        d.bbox_width AS bboxWidth,d.bbox_height AS bboxHeight
        FROM detections d JOIN waste_types wt ON wt.id=d.waste_type_id
        WHERE d.detection_run_id=%s
        AND NOT (d.review_result='FALSE_NEGATIVE' AND d.confidence=0)
        ORDER BY d.id""", (row.get("runId"),),
    ) if row.get("runId") else []
    row["detections"] = detections if isinstance(detections, list) else []
    row["detectedClasses"] = sorted({item["className"] for item in row["detections"]})
    row["objectCount"] = len(row["detections"])
    confidences = [float(item["confidence"]) for item in row["detections"] if item.get("confidence") is not None]
    row["averageConfidence"] = sum(confidences) / len(confidences) if confidences else None
    return row


def find_reinspection_context(inspection_id: int, user_id: int, is_admin: bool) -> dict[str, Any] | None:
    permission = "" if is_admin else "AND i.inspector_id=%s"
    params = (inspection_id,) if is_admin else (inspection_id, user_id)
    row = fetch_query(
        f"""SELECT i.id AS inspectionId,r.id AS runId,r.model_name AS modelName,
        r.model_version AS modelVersion,am.external_id AS currentModelId,am.name AS currentModelName
        FROM inspections i
        LEFT JOIN detection_runs r ON r.id=(SELECT rr.id FROM detection_runs rr
          WHERE rr.inspection_id=i.id AND rr.status='SUCCEEDED' ORDER BY rr.id DESC LIMIT 1)
        LEFT JOIN ai_models am ON am.id=(SELECT model.id FROM ai_models model
          WHERE model.name=r.model_name OR model.external_id=r.model_name OR model.name=r.model_version
          ORDER BY model.is_selected DESC,model.id DESC LIMIT 1)
        WHERE i.id=%s AND i.deleted_at IS NULL {permission} LIMIT 1""", params, one=True,
    )
    if not isinstance(row, dict):
        return None
    detections = fetch_query(
        """SELECT d.id,wt.name_ko AS originalClassName,
        COALESCE(awt.name_ko,wt.name_ko) AS className,d.confidence,
        d.review_result AS reviewResult,d.review_status AS reviewStatus,
        (d.actual_waste_type_id IS NOT NULL AND d.actual_waste_type_id<>d.waste_type_id) AS classChanged,
        (d.review_result='FALSE_NEGATIVE' AND d.confidence=0) AS manuallyAdded
        FROM detections d JOIN waste_types wt ON wt.id=d.waste_type_id
        LEFT JOIN waste_types awt ON awt.id=d.actual_waste_type_id
        WHERE d.detection_run_id=%s ORDER BY d.id""", (row.get("runId"),),
    ) if row.get("runId") else []
    row["detections"] = detections if isinstance(detections, list) else []
    totals = {"truePositive": 0, "falsePositive": 0, "falseNegative": 0}
    class_totals: dict[str, dict[str, Any]] = {}
    confidences = []
    for item in row["detections"]:
        result = item.get("reviewResult")
        key = {"TRUE_POSITIVE": "truePositive", "FALSE_POSITIVE": "falsePositive", "FALSE_NEGATIVE": "falseNegative"}.get(result)
        class_name = item.get("className") or item.get("originalClassName")
        if key:
            totals[key] += 1
            values = class_totals.setdefault(class_name, {"className": class_name, "truePositive": 0, "falsePositive": 0, "falseNegative": 0})
            values[key] += 1
        if not item.get("manuallyAdded") and item.get("confidence") is not None:
            confidences.append(float(item["confidence"]))
    row["reviewSummary"] = {
        **totals,
        "byClass": sorted(class_totals.values(), key=lambda item: item["className"]),
        "manuallyAddedCount": sum(bool(item.get("manuallyAdded")) for item in row["detections"]),
        "changedClassCount": sum(bool(item.get("classChanged")) for item in row["detections"]),
        "averageAiConfidence": sum(confidences) / len(confidences) if confidences else None,
        "falseNegativeClasses": sorted({item["className"] for item in row["detections"] if item.get("reviewResult") == "FALSE_NEGATIVE"}),
        "falsePositiveClasses": sorted({item["originalClassName"] for item in row["detections"] if item.get("reviewResult") == "FALSE_POSITIVE"}),
    }
    return row
