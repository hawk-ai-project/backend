# backend/repository/climate_analytics_repository.py

from typing import Dict, Any, List
from common.db import fetch_query


def _weather_condition(weather_event: str | None) -> str:
    """기상 이벤트별 SQL 조건절"""
    if not weather_event or weather_event == "ALL":
        return ""
    # inspections 테이블의 weather_event 컬럼과 직접 비교
    return f"AND i.weather_event = '{weather_event}'"


def _season_month_condition(season: str | None) -> str:
    """계절에 따른 captured_at 월(Month) 필터 SQL 조건절 생성"""
    if not season or season == "ALL":
        return ""
    season_map = {
        "SPRING": "AND MONTH(i.captured_at) IN (3, 4, 5)",
        "SUMMER": "AND MONTH(i.captured_at) IN (6, 7, 8)",
        "FALL": "AND MONTH(i.captured_at) IN (9, 10, 11)",
        "WINTER": "AND MONTH(i.captured_at) IN (12, 1, 2)",
    }
    return season_map.get(season, "")


def get_climate_summary(
    start_date: str,
    end_date: str,
    location_id: int | None = None,
    season: str | None = None,
    weather_event: str | None = None,
) -> Dict[str, Any]:
    start_ts = f"{start_date} 00:00:00"
    end_ts = f"{end_date} 23:59:59"
    season_clause = _season_month_condition(season)
    weather_clause = _weather_condition(weather_event)

    # 1. 점검 건수 및 조치 완료 집계
    summary_sql = f"""
        SELECT 
            COUNT(DISTINCT i.id) AS total_inspections,
            COALESCE(SUM(CASE WHEN i.status = 'RESOLVED' THEN 1 ELSE 0 END), 0) AS resolved_count,
            DATEDIFF(%s, %s) + 1 AS total_days
        FROM inspections i
        LEFT JOIN locations l ON i.location_id = l.id
        LEFT JOIN regions r ON r.id = %s
        WHERE i.deleted_at IS NULL
          AND i.captured_at BETWEEN %s AND %s
          AND (%s IS NULL OR l.address LIKE CONCAT('%%', r.name, '%%'))
          {season_clause}
          {weather_clause}
    """
    summary_row = (
        fetch_query(
            summary_sql,
            (end_date, start_date, location_id, start_ts, end_ts, location_id),
            one=True,
        )
        or {}
    )

    total_inspections = summary_row.get("total_inspections", 0) or 0
    resolved_count = summary_row.get("resolved_count", 0) or 0
    total_days = max(summary_row.get("total_days", 1) or 1, 1)

    daily_avg = (
        round(total_inspections / total_days, 1) if total_inspections > 0 else 0.0
    )
    res_rate = (
        round((resolved_count / total_inspections) * 100, 1)
        if total_inspections > 0
        else 0.0
    )

    # 2. 총 탐지 건수
    det_sql = f"""
        SELECT COUNT(d.id) AS total_detections
        FROM detections d
        JOIN detection_runs dr ON d.detection_run_id = dr.id
        JOIN inspections i ON dr.inspection_id = i.id
        LEFT JOIN locations l ON i.location_id = l.id
        LEFT JOIN regions r ON r.id = %s
        WHERE i.deleted_at IS NULL
          AND dr.status = 'SUCCEEDED'
          AND i.captured_at BETWEEN %s AND %s
          AND (%s IS NULL OR l.address LIKE CONCAT('%%', r.name, '%%'))
          {season_clause}
          {weather_clause}
    """
    det_row = (
        fetch_query(det_sql, (location_id, start_ts, end_ts, location_id), one=True)
        or {}
    )
    total_detections = det_row.get("total_detections", 0) or 0

    # 3. 최다 탐지 폐기물 항목
    top_sql = f"""
        SELECT wt.name_ko AS name, COUNT(d.id) AS count
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
          {season_clause}
          {weather_clause}
        GROUP BY wt.id, wt.name_ko
        ORDER BY count DESC
        LIMIT 1
    """
    top_row = fetch_query(
        top_sql, (location_id, start_ts, end_ts, location_id), one=True
    )
    top_item = {"name": "-", "count": 0, "ratio": 0.0}
    if top_row and total_detections > 0:
        c = top_row.get("count", 0) or 0
        top_item = {
            "name": top_row.get("name"),
            "count": c,
            "ratio": round((c / total_detections) * 100, 1),
        }

    return {
        "totalInspections": total_inspections,
        "dailyAvgInspections": daily_avg,
        "totalDetections": total_detections,
        "resolutionRate": res_rate,
        "resolvedCount": resolved_count,
        "topDetectedItem": top_item,
    }


def get_climate_trends(
    start_date: str,
    end_date: str,
    location_id: int | None = None,
    season: str | None = None,
    weather_event: str | None = None,
) -> List[Dict[str, Any]]:
    start_ts = f"{start_date} 00:00:00"
    end_ts = f"{end_date} 23:59:59"
    season_clause = _season_month_condition(season)
    weather_clause = _weather_condition(weather_event)

    sql = f"""
        SELECT 
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
          {season_clause}
          {weather_clause}
        GROUP BY DATE(i.captured_at), DATE_FORMAT(i.captured_at, '%%m/%%d')
        ORDER BY DATE(i.captured_at) ASC
    """
    rows = fetch_query(sql, (location_id, start_ts, end_ts, location_id)) or []
    return [{"date": row["date"], "count": row["count"]} for row in rows]


def get_climate_waste_distribution(
    start_date: str,
    end_date: str,
    location_id: int | None = None,
    season: str | None = None,
    weather_event: str | None = None,
) -> List[Dict[str, Any]]:
    start_ts = f"{start_date} 00:00:00"
    end_ts = f"{end_date} 23:59:59"
    season_clause = _season_month_condition(season)
    weather_clause = _weather_condition(weather_event)

    sql = f"""
        SELECT wt.name_ko AS name, COUNT(d.id) AS count
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
          {season_clause}
          {weather_clause}
        GROUP BY wt.id, wt.name_ko
        ORDER BY count DESC
    """
    rows = fetch_query(sql, (location_id, start_ts, end_ts, location_id)) or []
    total = sum(r["count"] for r in rows)
    if total == 0:
        return []
    return [
        {
            "name": r["name"],
            "count": r["count"],
            "percentage": round((r["count"] / total) * 100, 1),
        }
        for r in rows
    ]


def get_climate_locations(
    start_date: str,
    end_date: str,
    location_id: int | None = None,
    season: str | None = None,
    weather_event: str | None = None,
) -> List[Dict[str, Any]]:
    start_ts = f"{start_date} 00:00:00"
    end_ts = f"{end_date} 23:59:59"
    season_clause = _season_month_condition(season)
    weather_clause = _weather_condition(weather_event)

    sql = f"""
        SELECT 
            r.id AS region_id,
            r.name AS region_name,
            l.name AS location_name,
            l.address,
            l.latitude,
            l.longitude,
            DATE_FORMAT(MAX(i.captured_at), '%%Y-%%m-%%d') AS date,
            COUNT(DISTINCT i.id) AS count,
            COUNT(d.id) AS detection_count
        FROM inspections i
        JOIN locations l ON i.location_id = l.id
        LEFT JOIN regions r ON (
            l.address LIKE CONCAT(r.name, '%%') 
            OR l.address LIKE CONCAT('%% ', r.name, '%%')
        ) AND r.is_active = TRUE
        LEFT JOIN detection_runs dr ON dr.inspection_id = i.id
        LEFT JOIN detections d ON d.detection_run_id = dr.id
        WHERE i.deleted_at IS NULL
          AND i.captured_at BETWEEN %s AND %s
          AND (%s IS NULL OR r.id = %s)
          AND l.latitude IS NOT NULL 
          AND l.longitude IS NOT NULL
          AND l.latitude != 0 
          AND l.longitude != 0
          {season_clause}
          {weather_clause}
        GROUP BY 
            r.id, r.name, l.id, l.name, l.address, l.latitude, l.longitude
    """
    rows = fetch_query(sql, (start_ts, end_ts, location_id, location_id)) or []
    return [
        {
            "id": row["region_id"] or 0,
            "region": row["region_name"] or "-",
            "name": row["location_name"] or row["address"],
            "address": row["address"],
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "date": row["date"],
            "count": int(row["count"]),
            "detectionCount": int(row["detection_count"] or 0),
        }
        for row in rows
    ]


def get_climate_regions() -> List[Dict[str, Any]]:
    sql = """
        SELECT r.id, r.name
        FROM regions r
        WHERE r.is_active = TRUE
          AND EXISTS (
              SELECT 1 FROM locations l 
              WHERE l.address LIKE CONCAT('%%', r.name, '%%')
          )
        ORDER BY r.sort_order ASC, r.name ASC
    """
    return fetch_query(sql) or []
