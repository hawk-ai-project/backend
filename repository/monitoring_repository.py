"""Aggregated operational, security, and usage monitoring queries."""

from datetime import datetime
from typing import Any

from common.db import fetch_query


def operational_stats() -> dict[str, Any]:
    row = fetch_query(
        """SELECT
          (SELECT COUNT(DISTINCT user_id) FROM activity_logs
             WHERE occurred_at >= UTC_TIMESTAMP() - INTERVAL 15 MINUTE AND user_id IS NOT NULL) AS onlineUsers,
          (SELECT COUNT(DISTINCT user_id) FROM activity_logs
             WHERE occurred_at >= UTC_DATE() AND user_id IS NOT NULL) AS dau,
          (SELECT COUNT(DISTINCT user_id) FROM activity_logs
             WHERE occurred_at >= UTC_TIMESTAMP() - INTERVAL 30 DAY AND user_id IS NOT NULL) AS mau,
          (SELECT COUNT(*) FROM activity_logs
             WHERE occurred_at >= UTC_DATE()) AS eventsToday,
          (SELECT COUNT(*) FROM activity_logs
             WHERE occurred_at >= UTC_TIMESTAMP() - INTERVAL 24 HOUR AND outcome = 'FAILURE') AS errors24h,
          (SELECT COUNT(*) FROM activity_logs
             WHERE occurred_at >= UTC_TIMESTAMP() - INTERVAL 24 HOUR
               AND category = 'AUTH' AND action = 'LOGIN' AND outcome <> 'SUCCESS') AS failedLogins24h,
          (SELECT COUNT(*) FROM activity_logs
             WHERE occurred_at >= UTC_TIMESTAMP() - INTERVAL 24 HOUR
               AND category = 'ADMIN' AND http_method <> 'GET' AND outcome = 'SUCCESS') AS auditChanges24h""",
        one=True,
    )
    return row if isinstance(row, dict) else {}


def recent_incidents(limit: int = 8) -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT id, request_id AS requestId, category, action, path,
                  status_code AS statusCode, outcome, duration_ms AS durationMs,
                  occurred_at AS occurredAt
           FROM activity_logs
           WHERE outcome = 'FAILURE' OR status_code >= 500
           ORDER BY occurred_at DESC, id DESC LIMIT %s""",
        (limit,),
    )
    return rows if isinstance(rows, list) else []


def suspicious_sources(failed_login_threshold: int, limit: int = 10) -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT COALESCE(ip_address, 'UNKNOWN') AS ipAddress,
                  COUNT(*) AS eventCount,
                  SUM(category = 'AUTH' AND action = 'LOGIN') AS failedLogins,
                  COUNT(DISTINCT user_id) AS affectedUsers,
                  MAX(occurred_at) AS lastOccurredAt
           FROM activity_logs
           WHERE occurred_at >= UTC_TIMESTAMP() - INTERVAL 24 HOUR
             AND outcome IN ('DENIED', 'FAILURE')
           GROUP BY ip_address
           HAVING failedLogins >= %s OR eventCount >= %s
           ORDER BY eventCount DESC, lastOccurredAt DESC LIMIT %s""",
        (failed_login_threshold, failed_login_threshold * 2, limit),
    )
    return rows if isinstance(rows, list) else []


def feature_usage(limit: int = 12) -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT category, action, COUNT(*) AS count,
                  COUNT(DISTINCT user_id) AS uniqueUsers,
                  ROUND(AVG(duration_ms)) AS averageDurationMs
           FROM activity_logs
           WHERE occurred_at >= UTC_TIMESTAMP() - INTERVAL 30 DAY
             AND outcome = 'SUCCESS'
           GROUP BY category, action
           ORDER BY count DESC LIMIT %s""",
        (limit,),
    )
    return rows if isinstance(rows, list) else []


def daily_report(days: int = 14) -> list[dict[str, Any]]:
    rows = fetch_query(
        """SELECT DATE(occurred_at) AS reportDate, COUNT(*) AS events,
                  COUNT(DISTINCT user_id) AS activeUsers,
                  SUM(outcome = 'FAILURE') AS failures,
                  SUM(outcome = 'DENIED') AS denied
           FROM activity_logs
           WHERE occurred_at >= UTC_DATE() - INTERVAL %s DAY
           GROUP BY DATE(occurred_at) ORDER BY reportDate""",
        (days,),
    )
    return rows if isinstance(rows, list) else []
