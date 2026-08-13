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


def find_data_items(page: int, page_size: int, keyword: str | None,
                    class_name: str | None, tag_ids: list[int],
                    result: str | None, review_status: str | None,
                    retraining: bool | None):
    clauses, params = ["i.deleted_at IS NULL", "r.status='SUCCEEDED'"], []
    if keyword:
        clauses.append("(i.title LIKE %s OR l.name LIKE %s)")
        term=f"%{keyword}%"; params.extend([term,term])
    if class_name:
        clauses.append("EXISTS (SELECT 1 FROM detections dx JOIN waste_types wx ON wx.id=dx.waste_type_id WHERE dx.detection_run_id=r.id AND wx.name_ko=%s)")
        params.append(class_name)
    if result:
        clauses.append("EXISTS (SELECT 1 FROM detections dx WHERE dx.detection_run_id=r.id AND dx.review_result=%s)")
        params.append(result)
    if review_status:
        clauses.append("EXISTS (SELECT 1 FROM detections dx WHERE dx.detection_run_id=r.id AND dx.review_status=%s)")
        params.append(review_status)
    if retraining is not None:
        clauses.append("EXISTS (SELECT 1 FROM detections dx WHERE dx.detection_run_id=r.id AND dx.retraining_candidate=%s)")
        params.append(retraining)
    for tag_id in tag_ids:
        clauses.append("EXISTS (SELECT 1 FROM inspection_data_tags itx WHERE itx.inspection_id=i.id AND itx.tag_id=%s)")
        params.append(tag_id)
    where=" AND ".join(clauses)
    count=fetch_query(
        f"""SELECT COUNT(*) total FROM inspections i LEFT JOIN locations l ON l.id=i.location_id
        JOIN detection_runs r ON r.id=(SELECT rr.id FROM detection_runs rr WHERE rr.inspection_id=i.id AND rr.status='SUCCEEDED' ORDER BY rr.created_at DESC LIMIT 1)
        WHERE {where}""", tuple(params), one=True,
    )
    rows=fetch_query(
        f"""SELECT i.id AS inspectionId,i.title,l.name AS location,i.captured_at AS capturedAt,
        r.model_name AS modelName,r.model_version AS modelVersion,r.source_image_id AS imageId,
        (SELECT COUNT(*) FROM detections d WHERE d.detection_run_id=r.id) AS detectionCount,
        (SELECT ROUND(MAX(d.confidence),4) FROM detections d WHERE d.detection_run_id=r.id) AS maxConfidence,
        (SELECT GROUP_CONCAT(DISTINCT wt.name_ko ORDER BY wt.name_ko SEPARATOR ', ')
         FROM detections d JOIN waste_types wt ON wt.id=d.waste_type_id WHERE d.detection_run_id=r.id) AS classes,
        (SELECT GROUP_CONCAT(DISTINCT dt.name ORDER BY dt.name SEPARATOR ',')
         FROM inspection_data_tags idt JOIN data_tags dt ON dt.id=idt.tag_id WHERE idt.inspection_id=i.id) AS tags,
        (SELECT COUNT(*) FROM detections d WHERE d.detection_run_id=r.id AND d.retraining_candidate=TRUE)>0 AS retrainingCandidate,
        (SELECT COUNT(*) FROM detections d WHERE d.detection_run_id=r.id AND d.review_status='APPROVED')=
        (SELECT COUNT(*) FROM detections d WHERE d.detection_run_id=r.id) AS approved
        FROM inspections i LEFT JOIN locations l ON l.id=i.location_id
        JOIN detection_runs r ON r.id=(SELECT rr.id FROM detection_runs rr WHERE rr.inspection_id=i.id AND rr.status='SUCCEEDED' ORDER BY rr.created_at DESC LIMIT 1)
        WHERE {where} ORDER BY i.captured_at DESC,i.id DESC LIMIT %s OFFSET %s""",
        tuple(params+[page_size,(page-1)*page_size]),
    )
    items=rows if isinstance(rows,list) else []
    for item in items:
        item["tags"]=item["tags"].split(",") if item.get("tags") else []
    return items,int(count["total"]) if count else 0


def find_data_detail(inspection_id: int):
    inspection=fetch_query(
        """SELECT i.id AS inspectionId,i.title,l.name AS location,i.captured_at AS capturedAt,
        r.id AS runId,r.model_name AS modelName,r.model_version AS modelVersion
        FROM inspections i LEFT JOIN locations l ON l.id=i.location_id
        JOIN detection_runs r ON r.id=(SELECT rr.id FROM detection_runs rr
          WHERE rr.inspection_id=i.id AND rr.status='SUCCEEDED' ORDER BY rr.created_at DESC LIMIT 1)
        WHERE i.id=%s AND i.deleted_at IS NULL""",(inspection_id,),one=True,
    )
    if not isinstance(inspection,dict):
        return None
    detections=fetch_query(BASE_SELECT+" WHERE r.id=%s ORDER BY d.id",(inspection["runId"],))
    tags=fetch_query(
        """SELECT t.id,t.name,c.code AS categoryCode FROM inspection_data_tags it
        JOIN data_tags t ON t.id=it.tag_id JOIN data_tag_categories c ON c.id=t.category_id
        WHERE it.inspection_id=%s ORDER BY c.code,t.name""",(inspection_id,),
    )
    inspection["detections"]=detections if isinstance(detections,list) else []
    inspection["tags"]=tags if isinstance(tags,list) else []
    return inspection


def delete_detection(detection_id: int) -> bool:
    return execute_query("DELETE FROM detections WHERE id=%s",(detection_id,))>0


def list_data_tags():
    rows=fetch_query(
        """SELECT t.id,t.name,t.description,c.code AS categoryCode,c.name AS categoryName,
        COUNT(idt.inspection_id) AS usageCount,t.created_at AS createdAt
        FROM data_tags t JOIN data_tag_categories c ON c.id=t.category_id
        LEFT JOIN inspection_data_tags idt ON idt.tag_id=t.id
        GROUP BY t.id,t.name,t.description,c.code,c.name,t.created_at
        ORDER BY c.name,t.name"""
    )
    return rows if isinstance(rows,list) else []


def create_data_tag(name: str, category_code: str, description: str | None, admin_id: int):
    normalized="-".join(name.strip().lower().split())
    category=fetch_query("SELECT id FROM data_tag_categories WHERE code=%s",(category_code,),one=True)
    if not category:
        return 0
    return execute_query(
        """INSERT INTO data_tags(category_id,name,normalized_name,description,created_by)
        VALUES(%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id),
        description=VALUES(description)""",
        (category["id"],name.strip(),normalized,description,admin_id),
    )


def bulk_data_action(inspection_ids: list[int], action: str, tag_ids: list[int], admin_id: int) -> int:
    connection=engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            placeholders=",".join(["%s"]*len(inspection_ids))
            if action in {"ADD_TAG","HARD_EXAMPLE"}:
                selected_tags=tag_ids
                if action=="HARD_EXAMPLE":
                    cursor.execute("SELECT id FROM data_tags WHERE normalized_name='hard-example'")
                    row=cursor.fetchone(); selected_tags=[row[0]] if row else []
                for inspection_id in inspection_ids:
                    for tag_id in selected_tags:
                        cursor.execute(
                            """INSERT IGNORE INTO inspection_data_tags(inspection_id,tag_id,created_by)
                            VALUES(%s,%s,%s)""",(inspection_id,tag_id,admin_id),
                        )
            elif action=="REMOVE_TAG" and tag_ids:
                tag_placeholders=",".join(["%s"]*len(tag_ids))
                cursor.execute(f"DELETE FROM inspection_data_tags WHERE inspection_id IN ({placeholders}) AND tag_id IN ({tag_placeholders})",tuple(inspection_ids+tag_ids))
            if action in {"RETRAIN","HARD_EXAMPLE","APPROVE","REJECT"}:
                assignments={
                    "RETRAIN":"d.retraining_candidate=TRUE",
                    "HARD_EXAMPLE":"d.retraining_candidate=TRUE",
                    "APPROVE":"d.review_status='APPROVED',d.reviewed_by=%s,d.reviewed_at=UTC_TIMESTAMP(6)",
                    "REJECT":"d.review_status='REJECTED',d.reviewed_by=%s,d.reviewed_at=UTC_TIMESTAMP(6)",
                }
                prefix_params=[admin_id] if action in {"APPROVE","REJECT"} else []
                cursor.execute(
                    f"""UPDATE detections d JOIN detection_runs r ON r.id=d.detection_run_id
                    SET {assignments[action]} WHERE r.inspection_id IN ({placeholders})""",
                    tuple(prefix_params+inspection_ids),
                )
            affected=cursor.rowcount
        connection.commit(); return affected
    except Exception:
        connection.rollback(); raise
    finally:
        connection.close()
