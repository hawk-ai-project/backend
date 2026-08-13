"""Queries for the administrator AI detection review workspace."""

from typing import Any

from common.db import engine, execute_query, fetch_query


BASE_SELECT = """SELECT d.id, r.inspection_id AS inspectionId, i.title,
 l.name AS location, i.captured_at AS detectedAt, wt.name_ko AS predictedClass,
 d.confidence, d.bbox_x AS bboxX, d.bbox_y AS bboxY,
 d.bbox_width AS bboxWidth, d.bbox_height AS bboxHeight,
 r.model_name AS modelName, r.model_version AS modelVersion,
 d.review_result AS reviewResult, d.review_status AS reviewStatus,
 awt.name_ko AS actualClass, d.error_reason AS errorReason,
 d.retraining_candidate AS retrainingCandidate, d.reviewed_at AS reviewedAt
 FROM detections d
 JOIN detection_runs r ON r.id = d.detection_run_id
 JOIN inspections i ON i.id = r.inspection_id AND i.deleted_at IS NULL
 LEFT JOIN locations l ON l.id = i.location_id
 JOIN waste_types wt ON wt.id = d.waste_type_id
 LEFT JOIN waste_types awt ON awt.id = d.actual_waste_type_id"""


def find_detections(page: int, page_size: int, keyword: str | None,
                    result: str | None, review_status: str | None,
                    class_name: str | None, min_confidence: float | None):
    clauses, params = [], []
    if keyword:
        clauses.append("(i.title LIKE %s OR l.name LIKE %s OR wt.name_ko LIKE %s)")
        term = f"%{keyword}%"
        params.extend([term, term, term])
    if result:
        clauses.append("d.review_result = %s")
        params.append(result)
    if review_status:
        clauses.append("d.review_status = %s")
        params.append(review_status)
    if class_name:
        clauses.append("wt.name_ko = %s")
        params.append(class_name)
    if min_confidence is not None:
        clauses.append("d.confidence >= %s")
        params.append(min_confidence)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    count = fetch_query(
        "SELECT COUNT(*) AS total FROM (" + BASE_SELECT + where + ") q",
        tuple(params), one=True,
    )
    rows = fetch_query(
        BASE_SELECT + where + " ORDER BY i.captured_at DESC, d.id DESC LIMIT %s OFFSET %s",
        tuple(params + [page_size, (page - 1) * page_size]),
    )
    return (rows if isinstance(rows, list) else [], int(count["total"]) if count else 0)


def find_detection(detection_id: int) -> dict[str, Any] | None:
    row = fetch_query(BASE_SELECT + " WHERE d.id = %s", (detection_id,), one=True)
    return row if isinstance(row, dict) else None


def find_waste_types() -> list[dict[str, Any]]:
    rows = fetch_query(
        "SELECT id, code, name_ko AS name FROM waste_types WHERE is_active = TRUE ORDER BY name_ko"
    )
    return rows if isinstance(rows, list) else []


def find_or_create_waste_type(name: str) -> int:
    code = name.strip().upper().replace(" ", "_")[:50]
    return execute_query(
        """INSERT INTO waste_types (code, name_ko, name_en) VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)""",
        (code, name.strip()[:100], name.strip()[:100]),
    )


def update_review(detection_id: int, payload, reviewer_id: int, actual_type_id: int | None) -> bool:
    bbox = payload.bbox
    bbox_sql = ""
    params: list[Any] = [
        payload.result, payload.reviewStatus, actual_type_id,
        payload.errorReason.strip() if payload.errorReason else None,
        payload.retrainingCandidate, reviewer_id,
    ]
    if bbox is not None:
        bbox_sql = ", bbox_x=%s, bbox_y=%s, bbox_width=%s, bbox_height=%s"
        params.extend(bbox)
    params.append(detection_id)
    return execute_query(
        """UPDATE detections SET review_result=%s, review_status=%s,
        actual_waste_type_id=%s, error_reason=%s, retraining_candidate=%s,
        reviewed_by=%s, reviewed_at=UTC_TIMESTAMP(6)""" + bbox_sql + " WHERE id=%s",
        tuple(params),
    ) > 0


def create_missed_detection(inspection_id: int, actual_type_id: int, bbox: list[float],
                            reason: str | None, candidate: bool, reviewer_id: int) -> int:
    run = fetch_query(
        """SELECT id FROM detection_runs WHERE inspection_id=%s AND status='SUCCEEDED'
        ORDER BY created_at DESC LIMIT 1""", (inspection_id,), one=True,
    )
    if not run:
        return 0
    return execute_query(
        """INSERT INTO detections
        (detection_run_id, waste_type_id, confidence, bbox_x, bbox_y, bbox_width,
         bbox_height, review_result, review_status, actual_waste_type_id,
         error_reason, retraining_candidate, reviewed_by, reviewed_at)
        VALUES (%s, %s, 0, %s, %s, %s, %s, 'FALSE_NEGATIVE', 'REVIEWED',
                %s, %s, %s, %s, UTC_TIMESTAMP(6))""",
        (run["id"], actual_type_id, *bbox, actual_type_id, reason, candidate, reviewer_id),
    )


def statistics() -> dict[str, Any]:
    totals = fetch_query(
        """SELECT COUNT(*) total,
        SUM(review_result='UNREVIEWED') unreviewed,
        SUM(review_result='TRUE_POSITIVE') truePositive,
        SUM(review_result='FALSE_POSITIVE') falsePositive,
        SUM(review_result='FALSE_NEGATIVE') falseNegative,
        SUM(retraining_candidate=TRUE) retrainingCandidates FROM detections""", one=True,
    ) or {}
    classes = fetch_query(
        """SELECT wt.name_ko name, COUNT(*) count FROM detections d
        JOIN waste_types wt ON wt.id=d.waste_type_id GROUP BY wt.id, wt.name_ko
        ORDER BY count DESC LIMIT 10"""
    )
    return {**totals, "classDistribution": classes or []}
