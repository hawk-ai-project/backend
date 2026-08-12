"""Append-only activity log writes and administrator monitoring queries."""

import json
from datetime import datetime
from typing import Any

import pymysql

from common.db import engine, fetch_query


def create(entry: dict[str, Any]) -> None:
    """Persist a request audit record without emitting its metadata to SQL debug logs."""
    connection = engine.raw_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                """INSERT INTO activity_logs
                   (request_id, user_id, session_id, category, action, http_method,
                    path, route_template, status_code, outcome, severity, duration_ms,
                    ip_address, user_agent, metadata, occurred_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                           %s, %s, %s, UTC_TIMESTAMP(6))""",
                (
                    entry["requestId"], entry.get("userId"), entry.get("sessionId"),
                    entry["category"], entry["action"], entry["httpMethod"],
                    entry["path"], entry.get("routeTemplate"), entry["statusCode"],
                    entry["outcome"], entry["severity"], entry["durationMs"],
                    entry.get("ipAddress"), entry.get("userAgent"),
                    json.dumps(entry.get("metadata") or {}, ensure_ascii=False),
                ),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def summary(since: datetime) -> dict[str, Any]:
    row = fetch_query(
        """SELECT COUNT(*) AS totalEvents,
                  COUNT(DISTINCT user_id) AS activeUsers,
                  COALESCE(SUM(outcome = 'FAILURE'), 0) AS failedEvents,
                  COALESCE(SUM(outcome = 'DENIED'), 0) AS deniedEvents,
                  COALESCE(ROUND(AVG(duration_ms)), 0) AS averageDurationMs,
                  COALESCE(MAX(duration_ms), 0) AS maxDurationMs
           FROM activity_logs WHERE occurred_at >= %s""",
        (since,), one=True,
    )
    return row if isinstance(row, dict) else {}


def hourly_trend(since: datetime) -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT DATE_FORMAT(occurred_at, '%%Y-%%m-%%d %%H:00:00') AS bucket,
                  COUNT(*) AS total,
                  COALESCE(SUM(outcome = 'FAILURE'), 0) AS failures,
                  COALESCE(SUM(outcome = 'DENIED'), 0) AS denied,
                  COUNT(DISTINCT user_id) AS activeUsers
           FROM activity_logs
           WHERE occurred_at >= %s
           GROUP BY DATE_FORMAT(occurred_at, '%%Y-%%m-%%d %%H:00:00')
           ORDER BY bucket""",
        (since,),
    )
    return rows if isinstance(rows, list) else []


def top_actions(since: datetime, limit: int = 8) -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT category, action, COUNT(*) AS count,
                  COALESCE(SUM(outcome = 'FAILURE'), 0) AS failures
           FROM activity_logs
           WHERE occurred_at >= %s
           GROUP BY category, action
           ORDER BY count DESC, category, action
           LIMIT %s""",
        (since, limit),
    )
    return rows if isinstance(rows, list) else []


def find_all(
    page: int,
    page_size: int,
    from_at: datetime,
    to_at: datetime,
    category: str | None,
    outcome: str | None,
    user_id: int | None,
    keyword: str | None,
) -> tuple[list[dict[str, Any]], int]:
    where = "WHERE al.occurred_at >= %s AND al.occurred_at <= %s"
    params: list[Any] = [from_at, to_at]
    if category:
        where += " AND al.category = %s"
        params.append(category)
    if outcome:
        where += " AND al.outcome = %s"
        params.append(outcome)
    if user_id is not None:
        where += " AND al.user_id = %s"
        params.append(user_id)
    if keyword:
        where += " AND (u.name LIKE %s OR u.email LIKE %s OR al.path LIKE %s OR al.request_id = %s)"
        pattern = f"%{keyword}%"
        params.extend((pattern, pattern, pattern, keyword))

    count = fetch_query(
        f"""SELECT COUNT(*) AS total FROM activity_logs al
            LEFT JOIN users u ON u.id = al.user_id {where}""",
        tuple(params), one=True,
    )
    rows = fetch_query(
        f"""SELECT al.id, al.request_id AS requestId, al.user_id AS userId,
                   u.name AS userName, u.email AS userEmail,
                   al.category, al.action, al.http_method AS httpMethod,
                   al.path, al.route_template AS routeTemplate,
                   al.status_code AS statusCode, al.outcome, al.severity,
                   al.duration_ms AS durationMs, al.ip_address AS ipAddress,
                   al.user_agent AS userAgent, al.metadata, al.occurred_at AS occurredAt
            FROM activity_logs al
            LEFT JOIN users u ON u.id = al.user_id
            {where}
            ORDER BY al.occurred_at DESC, al.id DESC
            LIMIT %s OFFSET %s""",
        (*params, page_size, (page - 1) * page_size),
    )
    total = int(count["total"]) if isinstance(count, dict) else 0
    return (rows if isinstance(rows, list) else []), total
