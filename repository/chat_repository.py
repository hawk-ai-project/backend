from typing import Any

from common.db import fetch_query


def find_location_names() -> list[str]:
    rows = fetch_query("SELECT name FROM locations WHERE is_active = TRUE ORDER BY LENGTH(name) DESC")
    return [row["name"] for row in rows] if isinstance(rows, list) else []


def find_waste_names() -> list[str]:
    rows = fetch_query("SELECT name_ko FROM waste_types WHERE is_active = TRUE ORDER BY LENGTH(name_ko) DESC")
    return [row["name_ko"] for row in rows] if isinstance(rows, list) else []


def find_inspection_history(
    *,
    limit: int,
    user_id: int,
    is_admin: bool,
    location: str | None = None,
    waste: str | None = None,
) -> list[dict[str, Any]]:
    where = ["i.deleted_at IS NULL"]
    params: list[Any] = []
    if not is_admin:
        where.append("i.inspector_id = %s")
        params.append(user_id)
    if location:
        where.append("l.name LIKE %s")
        params.append(f"%{location}%")
    if waste:
        where.append(
            """EXISTS (
                SELECT 1
                FROM detection_runs filter_run
                JOIN detections filter_detection ON filter_detection.detection_run_id = filter_run.id
                JOIN waste_types filter_waste ON filter_waste.id = filter_detection.waste_type_id
                WHERE filter_run.inspection_id = i.id
                  AND filter_run.status = 'SUCCEEDED'
                  AND filter_waste.name_ko LIKE %s
            )"""
        )
        params.append(f"%{waste}%")

    rows = fetch_query(
        f"""SELECT i.id, i.title, COALESCE(l.name, '미지정 위치') AS location,
                   i.status, i.priority, i.captured_at AS capturedAt,
                   i.notes, i.ai_opinion AS aiOpinion, u.name AS inspectorName,
                   COALESCE(waste_summary.summary, '탐지 결과 없음') AS wasteSummary,
                   COALESCE(waste_summary.detections, JSON_ARRAY()) AS detections,
                   (SELECT image.id
                    FROM inspection_images image
                    WHERE image.inspection_id = i.id
                    ORDER BY image.kind = 'ANNOTATED' DESC, image.id DESC
                    LIMIT 1) AS imageId
            FROM inspections i
            LEFT JOIN locations l ON l.id = i.location_id
            JOIN users u ON u.id = i.inspector_id
            LEFT JOIN (
                SELECT counted.inspection_id,
                       GROUP_CONCAT(
                           CONCAT(wt.name_ko, ' ', counted.detected_count, '개')
                           ORDER BY wt.name_ko SEPARATOR ', '
                       ) AS summary,
                       JSON_ARRAYAGG(
                           JSON_OBJECT('className', wt.name_ko, 'count', counted.detected_count)
                       ) AS detections
                FROM (
                    SELECT dr.inspection_id, d.waste_type_id, COUNT(*) AS detected_count
                    FROM detection_runs dr
                    JOIN detections d ON d.detection_run_id = dr.id
                    WHERE dr.status = 'SUCCEEDED'
                    GROUP BY dr.inspection_id, d.waste_type_id
                ) counted
                JOIN waste_types wt ON wt.id = counted.waste_type_id
                GROUP BY counted.inspection_id
            ) waste_summary ON waste_summary.inspection_id = i.id
            WHERE {' AND '.join(where)}
            ORDER BY i.captured_at DESC, i.id DESC
            LIMIT %s""",
        (*params, limit),
    )
    return rows if isinstance(rows, list) else []


def find_accessible_inspection_image(
    inspection_id: int,
    user_id: int,
    is_admin: bool,
) -> dict[str, Any] | None:
    permission = "" if is_admin else "AND i.inspector_id = %s"
    params = (inspection_id,) if is_admin else (inspection_id, user_id)
    row = fetch_query(
        f"""SELECT image.id, image.inspection_id AS inspectionId, image.storage_key AS storageKey,
                   image.original_name AS originalName, image.mime_type AS mimeType,
                   image.byte_size AS byteSize
            FROM inspections i
            JOIN inspection_images image ON image.inspection_id = i.id
            WHERE i.id = %s AND i.deleted_at IS NULL {permission}
            ORDER BY image.kind = 'ANNOTATED' DESC, image.id DESC
            LIMIT 1""",
        params,
        one=True,
    )
    return row if isinstance(row, dict) else None
