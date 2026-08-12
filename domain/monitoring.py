"""Administrator observability response and settings models."""

from typing import Any

from pydantic import BaseModel, Field


class MonitoringSettings(BaseModel):
    cpuThreshold: int = Field(default=90, ge=10, le=100)
    memoryThreshold: int = Field(default=90, ge=10, le=100)
    diskThreshold: int = Field(default=90, ge=10, le=100)
    errorRateThreshold: float = Field(default=5, ge=0.1, le=100)
    failedLoginThreshold: int = Field(default=5, ge=2, le=100)
    logRetentionDays: int = Field(default=180, ge=7, le=2555)


class MonitoringOverview(BaseModel):
    generatedAt: str
    dashboard: dict[str, Any]
    system: dict[str, Any]
    services: list[dict[str, Any]]
    alerts: list[dict[str, Any]]
    recentIncidents: list[dict[str, Any]]
    security: dict[str, Any]
    reports: dict[str, Any]
    settings: MonitoringSettings
