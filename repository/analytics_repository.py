from typing import Dict, Any, List
from common.db import fetch_query


def get_analytics_summary(start_date: str, end_date: str, location_id: int | None = None) -> Dict[str, Any]:
    """
    지정된 기간 및 장소에 따른 KPI 통계 요약을 산출합니다.
    """
    start_ts = f"{start_date} 00:00:00"
    end_ts = f"{end_date} 23:59:59"

    # 1. 점검 및 조치 상태 집계 (% -> %% 로 이스케이프 처리)
    summary_sql = """
        SELECT /* get_analytics_summary.summary_sql */
            COUNT(DISTINCT i.id) AS total_inspections,
            COALESCE(SUM(CASE WHEN i.status = 'RESOLVED' THEN 1 ELSE 0 END), 0) AS resolved_count,
            DATEDIFF(%s, %s) + 1 AS total_days
        FROM inspections i
        LEFT JOIN locations l ON i.location_id = l.id
        LEFT JOIN regions r ON r.id = %s
        WHERE i.deleted_at IS NULL
          AND i.captured_at BETWEEN %s AND %s
          AND (%s IS NULL OR l.address LIKE CONCAT('%%', r.name, '%%'))
    """
    summary_row = fetch_query(
        summary_sql,
        (end_date, start_date, location_id, start_ts, end_ts, location_id),
        one=True
    ) or {}

    total_inspections = summary_row.get("total_inspections", 0) or 0
    resolved_count = summary_row.get("resolved_count", 0) or 0
    total_days = max(summary_row.get("total_days", 1) or 1, 1)

    daily_avg_inspections = round(total_inspections / total_days, 1) if total_inspections > 0 else 0.0
    resolution_rate = round((resolved_count / total_inspections) * 100, 1) if total_inspections > 0 else 0.0

    # 2. 총 탐지 건수 집계
    detection_count_sql = """
        SELECT /* get_analytics_summary.detection_count_sql */
            COUNT(d.id) AS total_detections
        FROM detections d
        JOIN detection_runs dr ON d.detection_run_id = dr.id
        JOIN inspections i ON dr.inspection_id = i.id
        LEFT JOIN locations l ON i.location_id = l.id
        LEFT JOIN regions r ON r.id = %s
        WHERE i.deleted_at IS NULL
          AND dr.status = 'SUCCEEDED'
          AND i.captured_at BETWEEN %s AND %s
          AND (%s IS NULL OR l.address LIKE CONCAT('%%', r.name, '%%'))
    """
    det_row = fetch_query(
        detection_count_sql,
        (location_id, start_ts, end_ts, location_id),
        one=True
    ) or {}
    total_detections = det_row.get("total_detections", 0) or 0

    # 3. 최다 탐지 항목 (Top Detected Waste Item)
    top_item_sql = """
        SELECT /* get_analytics_summary.top_item_sql */
            wt.name_ko AS name,
            COUNT(d.id) AS count
        FROM detections d
        JOIN waste_types wt ON d.waste_type_id = wt.id
        JOIN detection_runs dr ON d.detection_run_id = dr.id
        JOIN inspections i ON dr.inspection_id = i.id
        LEFT JOIN locations l ON i.location_id = l.id
        LEFT JOIN regions r ON r.id = %s
        WHERE i.deleted_at IS NULL
          AND dr.status = 'SUCCEEDED'
          AND i.captured_at BETWEEN %s AND %s
          AND (%s IS NULL OR l.address LIKE CONCAT('%%', r.name, '%%'))
        GROUP BY wt.id, wt.name_ko
        ORDER BY count DESC
        LIMIT 1
    """
    top_row = fetch_query(
        top_item_sql,
        (location_id, start_ts, end_ts, location_id),
        one=True
    )

    top_detected_item = {"name": "-", "count": 0, "ratio": 0.0}
    if top_row and total_detections > 0:
        top_count = top_row.get("count", 0) or 0
        top_detected_item = {
            "name": top_row.get("name"),
            "count": top_count,
            "ratio": round((top_count / total_detections) * 100, 1),
        }

    return {
        "totalInspections": total_inspections,
        "dailyAvgInspections": daily_avg_inspections,
        "totalDetections": total_detections,
        "resolutionRate": resolution_rate,
        "resolvedCount": resolved_count,
        "topDetectedItem": top_detected_item,
    }


def get_daily_trends(start_date: str, end_date: str, location_id: int | None = None) -> List[Dict[str, Any]]:
    """일자별 탐지 추이 데이터를 조회합니다."""
    start_ts = f"{start_date} 00:00:00"
    end_ts = f"{end_date} 23:59:59"

    sql = """
        SELECT /* get_daily_trends.sql */
            DATE_FORMAT(i.captured_at, '%%m/%%d') AS date,
            COUNT(d.id) AS count
        FROM inspections i
        JOIN detection_runs dr ON i.id = dr.inspection_id
        JOIN detections d ON dr.id = d.detection_run_id
        LEFT JOIN locations l ON i.location_id = l.id
        LEFT JOIN regions r ON r.id = %s
        WHERE i.deleted_at IS NULL
          AND dr.status = 'SUCCEEDED'
          AND i.captured_at BETWEEN %s AND %s
          AND (%s IS NULL OR l.address LIKE CONCAT('%%', r.name, '%%'))
        GROUP BY DATE(i.captured_at), DATE_FORMAT(i.captured_at, '%%m/%%d')
        ORDER BY DATE(i.captured_at) ASC
    """
    rows = fetch_query(sql, (location_id, start_ts, end_ts, location_id)) or []
    return [{"date": row["date"], "count": row["count"]} for row in rows]


def get_waste_distribution(start_date: str, end_date: str, location_id: int | None = None) -> List[Dict[str, Any]]:
    """폐기물 종류별 분포 비율 데이터를 조회합니다."""
    start_ts = f"{start_date} 00:00:00"
    end_ts = f"{end_date} 23:59:59"

    sql = """
        SELECT /* get_waste_distribution.sql */
            wt.name_ko AS name,
            COUNT(d.id) AS count
        FROM detections d
        JOIN waste_types wt ON d.waste_type_id = wt.id
        JOIN detection_runs dr ON d.detection_run_id = dr.id
        JOIN inspections i ON dr.inspection_id = i.id
        LEFT JOIN locations l ON i.location_id = l.id
        LEFT JOIN regions r ON r.id = %s
        WHERE i.deleted_at IS NULL
          AND dr.status = 'SUCCEEDED'
          AND i.captured_at BETWEEN %s AND %s
          AND (%s IS NULL OR l.address LIKE CONCAT('%%', r.name, '%%'))
        GROUP BY wt.id, wt.name_ko
        ORDER BY count DESC
    """
    rows = fetch_query(sql, (location_id, start_ts, end_ts, location_id)) or []

    total_count = sum(row["count"] for row in rows)
    if total_count == 0:
        return []

    return [
        {
            "name": row["name"],
            "count": row["count"],
            "percentage": round((row["count"] / total_count) * 100, 1),
        }
        for row in rows
    ]

def get_all_regions() -> List[Dict[str, Any]]:
    """드롭다운 표시를 위한 전체 활성화 지역 목록을 조회합니다."""
    sql = """
        SELECT /* get_all_regions.sql */
            r.id,
            r.name
        FROM regions r
        WHERE r.is_active = TRUE
        AND EXISTS (
            SELECT 1 
            FROM locations l 
            WHERE l.address LIKE CONCAT('%%', r.name, '%%')
        )
        ORDER BY r.sort_order ASC, r.name ASC;
    """
    rows = fetch_query(sql) or []

    return [
        {
            "id": row["id"],
            "name": row["name"],
        }
        for row in rows
    ]