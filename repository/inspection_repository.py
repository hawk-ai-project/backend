from typing import Any
import json
from datetime import datetime, timedelta;

from common.db import engine, execute_query, fetch_query


def find_active_assignees() -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT u.id, u.name, r.code AS role
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.deleted_at IS NULL AND u.status = 'ACTIVE'
          AND r.code <> 'USER'
        ORDER BY u.name, u.id"""
    )
    return rows if isinstance(rows, list) else []

def find_or_create_location(
    name: str, user_id: int, latitude: float | None = None, longitude: float | None = None, address: str | None = None
) -> int:
    # 중복 검사(SELECT) 없이 무조건 locations 테이블에 새로운 행을 추가
    return execute_query(
        "INSERT INTO locations (name, address, latitude, longitude, created_by) VALUES (%s, %s, %s, %s, %s)",
        (name, address, latitude, longitude, user_id),
    )


def create_inspection(
    location_id: int,
    user_id: int,
    title: str,
    notes: str | None,
    status: str = "REVIEW_REQUIRED",
) -> int:

    kst_now = datetime.utcnow() + timedelta(hours=9)
    formatted_time = kst_now.strftime('%Y-%m-%d %H:%M:%S')

    return execute_query(
        """INSERT INTO inspections
        (location_id, inspector_id, title, notes, status, priority, captured_at, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, 'MEDIUM', %s, %s, %s)""",
        (location_id, user_id, title, notes, status, formatted_time, formatted_time, formatted_time),
    )


def create_inspection_image(inspection_id: int, kind: str, stored: dict[str, Any]) -> int:
    return execute_query(
        """INSERT INTO inspection_images
        (inspection_id, kind, storage_key, original_name, mime_type, byte_size, sha256)
        VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (inspection_id, kind, stored["storageKey"], stored["originalName"],
         stored["mimeType"], stored["byteSize"], stored["sha256"]),
    )


def find_inspection_image_id(inspection_id: int, kind: str) -> int | None:
    row = fetch_query(
        """SELECT id FROM inspection_images
        WHERE inspection_id = %s AND kind = %s
        ORDER BY id DESC LIMIT 1""",
        (inspection_id, kind),
        one=True,
    )
    return int(row["id"]) if isinstance(row, dict) and row.get("id") is not None else None


def save_detection_result(
    inspection_id: int,
    source_image_id: int,
    annotated_image_id: int | None,
    analysis: dict[str, Any],
) -> int:
    """Persist one successful AI run and its normalized detections atomically."""
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO detection_runs
                (inspection_id, source_image_id, annotated_image_id, model_name,
                 model_version, status, inference_ms, raw_result, started_at, completed_at)
                VALUES (%s, %s, %s, %s, %s, 'SUCCEEDED', %s, %s,
                        UTC_TIMESTAMP(6), UTC_TIMESTAMP(6))""",
                (
                    inspection_id, source_image_id, annotated_image_id,
                    str(analysis.get("modelName") or "marine-waste-detector")[:100],
                    str(analysis.get("modelVersion") or "unknown")[:100],
                    analysis.get("inferenceMs"),
                    json.dumps(analysis, ensure_ascii=False),
                ),
            )
            run_id = int(cursor.lastrowid)
            for item in analysis.get("detections") or []:
                bbox = item.get("bbox") or []
                if len(bbox) != 4:
                    continue
                values = [float(value) for value in bbox]
                if any(value < 0 or value > 1 for value in values):
                    continue
                class_name = str(item.get("className") or "UNKNOWN").strip()
                class_code = class_name.upper().replace(" ", "_")[:50]
                cursor.execute(
                    """INSERT INTO waste_types (code, name_ko, name_en)
                    VALUES (%s, %s, %s)
                    ON DUPLICATE KEY UPDATE id = LAST_INSERT_ID(id)""",
                    (class_code, class_name[:100], class_name[:100]),
                )
                waste_type_id = int(cursor.lastrowid)
                cursor.execute(
                    """INSERT INTO detections
                    (detection_run_id, waste_type_id, confidence, bbox_x, bbox_y,
                     bbox_width, bbox_height)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (run_id, waste_type_id, float(item.get("confidence") or 0), *values),
                )
        connection.commit()
        return run_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def update_location_coordinates(location_id: int, latitude: float, longitude: float) -> None:
    execute_query(
        "UPDATE locations SET latitude = %s, longitude = %s WHERE id = %s",
        (latitude, longitude, location_id),
    )


def find_accessible_inspection(inspection_id: int, user_id: int, is_admin: bool) -> dict[str, Any] | None:
    permission = "" if is_admin else "AND i.inspector_id = %s"
    params = (inspection_id,) if is_admin else (inspection_id, user_id)
    row = fetch_query(
        f"""SELECT i.id
        FROM inspections i
        WHERE i.id = %s AND i.deleted_at IS NULL {permission}""",
        params,
        one=True,
    )
    return row if isinstance(row, dict) else None


def soft_delete_inspection(inspection_id: int) -> bool:
    affected = execute_query(
        """UPDATE inspections
        SET deleted_at = UTC_TIMESTAMP(6), updated_at = UTC_TIMESTAMP(6)
        WHERE id = %s AND deleted_at IS NULL""",
        (inspection_id,),
    )
    return affected > 0


def find_active_user(user_id: int) -> dict[str, Any] | None:
    row = fetch_query(
        """SELECT u.id, u.name, r.code AS role
        FROM users u
        JOIN roles r ON r.id = u.role_id
        WHERE u.id = %s AND u.deleted_at IS NULL
          AND u.status = 'ACTIVE' AND r.code <> 'USER'""",
        (user_id,),
        one=True,
    )
    return row if isinstance(row, dict) else None


def assign_inspection(inspection_id: int, assignee_id: int, created_by: int) -> None:
    existing = fetch_query(
        """SELECT id FROM inspection_actions
        WHERE inspection_id = %s
          AND action_type IN ('COLLECTION_REQUEST', 'COLLECTION')
          AND status <> 'CANCELLED'
        ORDER BY id DESC LIMIT 1""",
        (inspection_id,),
        one=True,
    )
    if isinstance(existing, dict):
        execute_query(
            """UPDATE inspection_actions
            SET assignee_id = %s, updated_at = UTC_TIMESTAMP(6)
            WHERE id = %s""",
            (assignee_id, existing["id"]),
        )
        return

    execute_query(
        """INSERT INTO inspection_actions
        (inspection_id, assignee_id, created_by, action_type, status, description)
        VALUES (%s, %s, %s, 'COLLECTION_REQUEST', 'OPEN', '현장 수거 담당자 배정')""",
        (inspection_id, assignee_id, created_by),
    )


def insert_inspection_record(payload, user_id: int, ai_opinion: str):
    # 프론트엔드에서 보낸 "35.1587,129.1604" 형태의 문자열을 반으로 쪼개서 위도/경도 숫자로 만들기
    lat, lon = 0.0, 0.0
    if payload.coordinates and "," in payload.coordinates:
        coords = payload.coordinates.split(",")
        lat = float(coords[0].strip())
        lon = float(coords[1].strip())

    kst_now = datetime.utcnow() + timedelta(hours=9)
    formatted_time = kst_now.strftime('%Y-%m-%d %H:%M:%S')

    print(f"🚀 [확인용] 파이썬이 만든 시간: {formatted_time}")

    # locations에 새 장소 추가
    execute_query(
        """INSERT INTO locations 
        (name, address, latitude, longitude, is_active, created_by, created_at, updated_at)
        VALUES (%s, %s, %s, 1, %s, %s, %s)""",
        (payload.location_name, lat, lon, user_id, formatted_time, formatted_time)
    )
    
    # inspections에 방금 만든 장소 번호(id)를 달아서 기록
    execute_query(
        """INSERT INTO inspections 
        (location_id, inspector_id, title, notes, ai_opinion, status, priority, captured_at, created_at, updated_at)
        VALUES (
            (SELECT id FROM locations WHERE name = %s ORDER BY created_at DESC LIMIT 1), 
            %s, %s, %s, %s, %s, 'MEDIUM', %s, %s, %s
        )""",
        (payload.location_name, user_id, payload.title, payload.notes, ai_opinion, payload.status, formatted_time, formatted_time, formatted_time)
    )


def _reinspection_permission(is_admin: bool) -> str:
    return "" if is_admin else "AND i.inspector_id = %s"


def find_reinspection_targets(user_id: int, is_admin: bool) -> list[dict[str, Any]]:
    permission = _reinspection_permission(is_admin)
    params = () if is_admin else (user_id,)
    rows = fetch_query(
        f"""SELECT i.id AS inspectionId, i.title, l.name AS location,
        i.captured_at AS capturedAt, i.status, u.name AS inspectorName,
        r.id AS runId, r.model_name AS modelName, r.model_version AS modelVersion,
        r.annotated_image_id AS annotatedImageId
        FROM inspections i
        LEFT JOIN locations l ON l.id=i.location_id
        LEFT JOIN users u ON u.id=i.inspector_id
        LEFT JOIN detection_runs r ON r.id=(SELECT rr.id FROM detection_runs rr
          WHERE rr.inspection_id=i.id AND rr.status='SUCCEEDED' ORDER BY rr.id DESC LIMIT 1)
        WHERE i.deleted_at IS NULL AND i.status='DRAFT' {permission}
        ORDER BY i.captured_at DESC, i.id DESC""", params,
    )
    items = rows if isinstance(rows, list) else []
    for item in items:
        item["detections"] = find_reinspection_detections(item.get("runId"))
    return items


def find_reinspection_detections(run_id: int | None) -> list[dict[str, Any]]:
    if not run_id:
        return []
    rows = fetch_query(
        """SELECT d.id, wt.name_ko AS originalClassName,
        COALESCE(awt.name_ko, wt.name_ko) AS className,
        d.confidence, d.bbox_x AS bboxX, d.bbox_y AS bboxY,
        d.bbox_width AS bboxWidth, d.bbox_height AS bboxHeight,
        d.review_result AS reviewResult, d.review_status AS reviewStatus,
        d.reviewed_at AS reviewedAt,
        (d.reviewed_at IS NOT NULL OR d.actual_waste_type_id IS NOT NULL
         OR d.review_status <> 'UNLABELED') AS modified,
        (d.review_result = 'FALSE_NEGATIVE' AND d.confidence = 0) AS manuallyAdded
        FROM detections d JOIN waste_types wt ON wt.id=d.waste_type_id
        LEFT JOIN waste_types awt ON awt.id=d.actual_waste_type_id
        WHERE d.detection_run_id=%s ORDER BY d.id""", (run_id),
    )
    return rows if isinstance(rows, list) else []


def find_reinspection_detail(inspection_id: int, user_id: int, is_admin: bool) -> dict[str, Any] | None:
    permission = _reinspection_permission(is_admin)
    params = (inspection_id,) if is_admin else (inspection_id, user_id)
    row = fetch_query(
        f"""SELECT i.id AS inspectionId, i.title, l.name AS location,
        i.captured_at AS capturedAt, i.status, r.id AS runId,
        r.model_name AS modelName, r.model_version AS modelVersion,
        am.external_id AS modelExternalId, am.name AS modelDisplayName,
        am.base_model AS modelBaseName, am.optimizer AS modelOptimizer,
        am.epochs AS modelEpochs, am.image_size AS modelImageSize,
        am.precision_score AS modelPrecision, am.recall_score AS modelRecall,
        am.map50 AS modelMap50, am.map50_95 AS modelMap50_95
        FROM inspections i LEFT JOIN locations l ON l.id=i.location_id
        LEFT JOIN detection_runs r ON r.id=(SELECT rr.id FROM detection_runs rr
          WHERE rr.inspection_id=i.id AND rr.status='SUCCEEDED' ORDER BY rr.id DESC LIMIT 1)
        LEFT JOIN ai_models am ON am.id=(SELECT model.id FROM ai_models model
          WHERE model.name=r.model_name OR model.external_id=r.model_name OR model.name=r.model_version
          ORDER BY model.is_selected DESC, model.id DESC LIMIT 1)
        WHERE i.id=%s AND i.deleted_at IS NULL AND i.status='DRAFT' {permission}""", params, one=True,
    )
    if not isinstance(row, dict):
        return None
    row["detections"] = find_reinspection_detections(row.get("runId"))
    return row


def approve_reinspection_targets(inspection_ids: list[int], user_id: int, is_admin: bool) -> int:
    placeholders = ",".join(["%s"] * len(inspection_ids))
    permission = "" if is_admin else "AND inspector_id=%s"
    params: list[Any] = list(inspection_ids)
    if not is_admin:
        params.append(user_id)
    return execute_query(
        f"""UPDATE inspections SET status='REVIEW_REQUIRED', updated_at=UTC_TIMESTAMP(6)
        WHERE id IN ({placeholders}) AND status='DRAFT' AND deleted_at IS NULL {permission}""", tuple(params),
    )


def find_active_waste_types() -> list[dict[str, Any]]:
    rows = fetch_query("SELECT id, code, name_ko AS name FROM waste_types WHERE is_active=TRUE ORDER BY sort_order, name_ko")
    return rows if isinstance(rows, list) else []


def save_reinspection_annotations(inspection_id: int, boxes, deleted_ids: list[int], reviewer_id: int) -> None:
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM detection_runs WHERE inspection_id=%s AND status='SUCCEEDED' ORDER BY id DESC LIMIT 1", (inspection_id,))
            run = cursor.fetchone()
            if not run:
                raise ValueError("성공한 AI 분석 결과가 없습니다.")
            run_id = int(run[0])
            for detection_id in deleted_ids:
                cursor.execute("DELETE FROM detections WHERE id=%s AND detection_run_id=%s", (detection_id, run_id))
            for box in boxes:
                name = box.className.strip()
                code = name.upper().replace(" ", "_")[:50]
                cursor.execute("""INSERT INTO waste_types (code,name_ko,name_en) VALUES (%s,%s,%s)
                    ON DUPLICATE KEY UPDATE id=LAST_INSERT_ID(id)""", (code,name[:100],name[:100]))
                waste_type_id = int(cursor.lastrowid)
                values = [float(value) for value in box.bbox]
                if box.id is not None and box.id > 0:
                    cursor.execute("""UPDATE detections SET actual_waste_type_id=%s,
                        bbox_x=%s,bbox_y=%s,bbox_width=%s,bbox_height=%s,
                        review_result='TRUE_POSITIVE',review_status='REVIEWED',
                        reviewed_by=%s,reviewed_at=UTC_TIMESTAMP(6)
                        WHERE id=%s AND detection_run_id=%s""",
                        (waste_type_id,*values,reviewer_id,box.id,run_id))
                else:
                    cursor.execute("""INSERT INTO detections
                        (detection_run_id,waste_type_id,confidence,bbox_x,bbox_y,bbox_width,bbox_height,
                         review_result,review_status,actual_waste_type_id,error_reason,retraining_candidate,reviewed_by,reviewed_at)
                        VALUES (%s,%s,0,%s,%s,%s,%s,'FALSE_NEGATIVE','REVIEWED',%s,
                                '재점검 수동 라벨링',TRUE,%s,UTC_TIMESTAMP(6))""",
                        (run_id,waste_type_id,*values,waste_type_id,reviewer_id))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def clear_previous_analysis(inspection_id: int) -> None:
    """해당 점검 건에 대해 이전에 실행된 AI 분석 결과(detections, detection_runs, ANNOTATED 이미지)를 삭제합니다."""
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            # 해당 점검에 연결된 모든 detection_runs ID 조회
            cursor.execute(
                "SELECT id FROM detection_runs WHERE inspection_id = %s",
                (inspection_id,)
            )
            run_rows = cursor.fetchall()
            run_ids = [row[0] for row in run_rows]

            if run_ids:
                placeholders = ",".join(["%s"] * len(run_ids))
                # detection_runs에 연결된 detections 레코드 삭제
                cursor.execute(
                    f"DELETE FROM detections WHERE detection_run_id IN ({placeholders})",
                    tuple(run_ids)
                )
                # detection_runs 레코드 삭제
                cursor.execute(
                    f"DELETE FROM detection_runs WHERE id IN ({placeholders})",
                    tuple(run_ids)
                )

            # 이전 ANNOTATED (분석 이미지) 메타데이터 삭제
            cursor.execute(
                "DELETE FROM inspection_images WHERE inspection_id = %s AND kind = 'ANNOTATED'",
                (inspection_id,)
            )

        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()