"""Operational health checks, alert evaluation, and monitoring reports."""

import shutil
import socket
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable

import httpx

from common.db import fetch_query
from config import settings as app_settings
from repository import monitoring_repository, settings_repository

try:
    import psutil
except ImportError:  # The API remains available while deployments install the new dependency.
    psutil = None


def get_settings() -> dict[str, Any]:
    values = settings_repository.get_all()
    return {
        "cpuThreshold": int(values["monitor_cpu_threshold"]),
        "memoryThreshold": int(values["monitor_memory_threshold"]),
        "diskThreshold": int(values["monitor_disk_threshold"]),
        "errorRateThreshold": float(values["monitor_error_rate_threshold"]),
        "failedLoginThreshold": int(values["monitor_failed_login_threshold"]),
        "logRetentionDays": int(values["activity_log_retention_days"]),
    }


def save_settings(payload, admin_id: int) -> dict[str, Any]:
    values = payload.model_dump()
    settings_repository.save_all({
        "monitor_cpu_threshold": values["cpuThreshold"],
        "monitor_memory_threshold": values["memoryThreshold"],
        "monitor_disk_threshold": values["diskThreshold"],
        "monitor_error_rate_threshold": values["errorRateThreshold"],
        "monitor_failed_login_threshold": values["failedLoginThreshold"],
        "activity_log_retention_days": values["logRetentionDays"],
    }, admin_id)
    return get_settings()


def _system_metrics() -> dict[str, Any]:
    disk = shutil.disk_usage("/")
    disk_percent = round(disk.used / disk.total * 100, 1) if disk.total else 0
    if psutil is None:
        return {"available": False, "cpuPercent": None, "memoryPercent": None,
                "diskPercent": disk_percent, "networkSentBytes": None,
                "networkReceivedBytes": None, "uptimeSeconds": None}
    memory = psutil.virtual_memory()
    network = psutil.net_io_counters()
    return {
        "available": True,
        "cpuPercent": round(psutil.cpu_percent(interval=0.05), 1),
        "memoryPercent": round(memory.percent, 1),
        "diskPercent": disk_percent,
        "networkSentBytes": network.bytes_sent,
        "networkReceivedBytes": network.bytes_recv,
        "uptimeSeconds": max(0, round(datetime.now().timestamp() - psutil.boot_time())),
    }


def _check(name: str, checker: Callable[[], None]) -> dict[str, Any]:
    started = perf_counter()
    try:
        checker()
        return {"name": name, "status": "UP", "responseTimeMs": round((perf_counter() - started) * 1000), "message": None}
    except Exception as error:
        return {"name": name, "status": "DOWN", "responseTimeMs": round((perf_counter() - started) * 1000), "message": type(error).__name__}


def _service_health() -> list[dict[str, Any]]:
    def database():
        fetch_query("SELECT 1 AS healthy", one=True)

    def ai_server():
        with httpx.Client(timeout=2, trust_env=False) as client:
            response = client.get(f"{app_settings.ai_server_url}/")
            response.raise_for_status()

    def object_storage():
        endpoint = app_settings.minio_endpoint.replace("http://", "").replace("https://", "").split("/", 1)[0]
        host, _, port = endpoint.partition(":")
        with socket.create_connection((host, int(port or (443 if app_settings.minio_secure else 9000))), timeout=2):
            pass

    return [
        {"name": "API", "status": "UP", "responseTimeMs": 0, "message": None},
        _check("Database", database), _check("AI Server", ai_server),
        _check("Object Storage", object_storage),
    ]


def get_overview() -> dict[str, Any]:
    monitoring_settings = get_settings()
    stats = monitoring_repository.operational_stats()
    system = _system_metrics()
    services = _service_health()
    total_24h_row = fetch_query(
        """SELECT COUNT(*) AS total, SUM(outcome = 'FAILURE') AS failures
           FROM activity_logs WHERE occurred_at >= UTC_TIMESTAMP() - INTERVAL 24 HOUR""",
        one=True,
    ) or {}
    total = int(total_24h_row.get("total") or 0)
    failures = int(total_24h_row.get("failures") or 0)
    error_rate = round(failures / total * 100, 2) if total else 0.0
    alerts: list[dict[str, Any]] = []

    for key, label, threshold_key in (
        ("cpuPercent", "CPU 사용률", "cpuThreshold"),
        ("memoryPercent", "메모리 사용률", "memoryThreshold"),
        ("diskPercent", "디스크 사용률", "diskThreshold"),
    ):
        value = system.get(key)
        threshold = monitoring_settings[threshold_key]
        if value is not None and value >= threshold:
            alerts.append({"severity": "CRITICAL" if value >= 95 else "WARNING", "title": f"{label} 임계값 초과", "message": f"현재 {value}% · 임계값 {threshold}%", "source": "SYSTEM"})
    if error_rate >= monitoring_settings["errorRateThreshold"]:
        alerts.append({"severity": "WARNING", "title": "API 실패율 임계값 초과", "message": f"최근 24시간 {error_rate}%", "source": "API"})
    for service in services:
        if service["status"] == "DOWN":
            alerts.append({"severity": "CRITICAL", "title": f"{service['name']} 연결 장애", "message": service["message"] or "응답 없음", "source": "SERVICE"})

    suspicious = monitoring_repository.suspicious_sources(monitoring_settings["failedLoginThreshold"])
    if suspicious:
        alerts.append({"severity": "WARNING", "title": "비정상 접근 패턴 감지", "message": f"의심 IP {len(suspicious)}개", "source": "SECURITY"})

    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "dashboard": {**stats, "serverStatus": "DEGRADED" if alerts else "HEALTHY", "errorRate24h": error_rate},
        "system": system,
        "services": services,
        "alerts": alerts,
        "recentIncidents": monitoring_repository.recent_incidents(),
        "security": {"suspiciousSources": suspicious, "failedLogins24h": int(stats.get("failedLogins24h") or 0)},
        "reports": {"featureUsage": monitoring_repository.feature_usage(), "daily": monitoring_repository.daily_report()},
        "settings": monitoring_settings,
    }
