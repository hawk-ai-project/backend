"""Safe request activity collection and monitoring aggregation."""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Any

from repository import activity_repository


logger = logging.getLogger(__name__)


def _classify(method: str, route: str) -> tuple[str, str]:
    path = route.lower()
    category = next((name for prefix, name in (
        ("/api/auth", "AUTH"), ("/api/boards", "BOARD"),
        ("/api/inspections", "INSPECTION"), ("/api/analytics", "ANALYTICS"),
        ("/api/admin", "ADMIN"), ("/api/chat", "CHAT"),
        ("/api/files", "FILE"),
    ) if path.startswith(prefix)), "SYSTEM")

    if path == "/api/auth/login":
        return category, "LOGIN"
    if path == "/api/auth/logout":
        return category, "LOGOUT"
    if path == "/api/auth/signup":
        return category, "SIGNUP"
    if "/role" in path:
        return category, "USER_ROLE_UPDATE"
    if "/status" in path:
        return category, "STATUS_UPDATE"
    if path.startswith("/api/admin/activity"):
        return category, "ACTIVITY_MONITOR_VIEW"

    operation = {
        "GET": "VIEW", "POST": "CREATE", "PUT": "UPDATE",
        "PATCH": "UPDATE", "DELETE": "DELETE",
    }.get(method.upper(), method.upper())
    resource = category if category != "SYSTEM" else "API"
    return category, f"{resource}_{operation}"


def record_http_request(
    *, request_id: str, method: str, path: str, route_template: str | None,
    status_code: int, duration_ms: int, user_id: int | None,
    session_id: str | None, ip_address: str | None, user_agent: str | None,
    query_keys: list[str],
) -> None:
    """Write best-effort telemetry; logging failure must never fail the user request."""
    try:
        category, action = _classify(method, route_template or path)
        outcome = "SUCCESS" if status_code < 400 else "DENIED" if status_code in (401, 403) else "FAILURE"
        severity = "ERROR" if status_code >= 500 else "WARNING" if status_code >= 400 else "INFO"
        activity_repository.create({
            "requestId": request_id,
            "userId": user_id,
            "sessionId": session_id,
            "category": category,
            "action": action,
            "httpMethod": method.upper()[:10],
            "path": path[:500],
            "routeTemplate": route_template[:500] if route_template else None,
            "statusCode": status_code,
            "outcome": outcome,
            "severity": severity,
            "durationMs": max(0, min(duration_ms, 4_294_967_295)),
            "ipAddress": ip_address[:45] if ip_address else None,
            "userAgent": user_agent[:500] if user_agent else None,
            "metadata": {"queryKeys": query_keys[:30]} if query_keys else {},
        })
    except Exception:
        logger.exception("Activity log persistence failed for request %s", request_id)


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def get_overview(hours: int = 24) -> dict[str, Any]:
    since = datetime.utcnow() - timedelta(hours=hours)
    summary = activity_repository.summary(since)
    total = int(summary.get("totalEvents") or 0)
    failures = int(summary.get("failedEvents") or 0)
    summary["errorRate"] = round((failures / total * 100), 2) if total else 0.0
    return {
        **summary,
        "windowHours": hours,
        "trend": activity_repository.hourly_trend(since),
        "topActions": activity_repository.top_actions(since),
    }


def get_logs(
    page: int, page_size: int, from_at: datetime | None, to_at: datetime | None,
    category: str | None, outcome: str | None, user_id: int | None,
    keyword: str | None,
) -> dict[str, Any]:
    end = _utc_naive(to_at) if to_at else datetime.utcnow()
    start = _utc_naive(from_at) if from_at else end - timedelta(days=7)
    if start > end:
        from service.auth_service import AuthError
        raise AuthError("조회 시작 시각은 종료 시각보다 늦을 수 없습니다.", 422)
    items, total = activity_repository.find_all(
        page, page_size, start, end, category, outcome, user_id, keyword,
    )
    for item in items:
        metadata = item.get("metadata")
        if isinstance(metadata, str):
            import json
            try:
                item["metadata"] = json.loads(metadata)
            except json.JSONDecodeError:
                item["metadata"] = {}
    return {
        "items": items, "page": page, "pageSize": page_size,
        "totalItems": total,
        "totalPages": math.ceil(total / page_size) if total else 0,
    }
