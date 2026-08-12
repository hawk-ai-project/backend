"""Response models for administrator APIs."""

from datetime import datetime

from typing import Any, Literal

from pydantic import BaseModel, Field


class AdminUser(BaseModel):
    id: int
    name: str
    email: str
    role: str
    status: str
    profileFileId: int | None = None
    lastLoginAt: datetime | None
    createdAt: datetime


class AdminUserPage(BaseModel):
    items: list[AdminUser]
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class DashboardStats(BaseModel):
    totalUsers: int
    activeUsers: int
    adminUsers: int
    newUsersThisMonth: int
    publishedBoards: int
    totalInspections: int
    recentUsers: list[AdminUser]


class AdminRole(BaseModel):
    code: str
    name: str
    description: str | None


class RoleUpdateRequest(BaseModel):
    roleCode: str = Field(min_length=1, max_length=30, pattern=r"^[A-Z_]+$")


AdminBoardStatus = Literal["DRAFT", "PUBLISHED", "HIDDEN"]


class AdminBoard(BaseModel):
    id: int
    title: str
    category: str
    authorId: int
    authorName: str
    status: AdminBoardStatus
    isNotice: bool
    viewCount: int
    publishedAt: datetime | None
    createdAt: datetime
    updatedAt: datetime


class AdminBoardPage(BaseModel):
    items: list[AdminBoard]
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class BoardStatusUpdateRequest(BaseModel):
    status: AdminBoardStatus


ActivityOutcome = Literal["SUCCESS", "DENIED", "FAILURE"]
ActivitySeverity = Literal["INFO", "WARNING", "ERROR"]


class ActivityLog(BaseModel):
    id: int
    requestId: str
    userId: int | None = None
    userName: str | None = None
    userEmail: str | None = None
    category: str
    action: str
    httpMethod: str
    path: str
    routeTemplate: str | None = None
    statusCode: int
    outcome: ActivityOutcome
    severity: ActivitySeverity
    durationMs: int
    ipAddress: str | None = None
    userAgent: str | None = None
    metadata: dict[str, Any] | None = None
    occurredAt: datetime


class ActivityLogPage(BaseModel):
    items: list[ActivityLog]
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class ActivityTrendPoint(BaseModel):
    bucket: datetime
    total: int
    failures: int
    denied: int
    activeUsers: int


class ActivityTopAction(BaseModel):
    category: str
    action: str
    count: int
    failures: int


class ActivityOverview(BaseModel):
    windowHours: int
    totalEvents: int
    activeUsers: int
    failedEvents: int
    deniedEvents: int
    averageDurationMs: int
    maxDurationMs: int
    errorRate: float
    trend: list[ActivityTrendPoint]
    topActions: list[ActivityTopAction]


class AdminSession(BaseModel):
    id: str
    userId: int
    userName: str
    userEmail: str
    userRole: str
    ipAddress: str | None = None
    userAgent: str | None = None
    status: Literal["ACTIVE", "EXPIRED", "REVOKED"]
    createdAt: datetime
    lastUsedAt: datetime | None = None
    expiresAt: datetime
    revokedAt: datetime | None = None


class AdminSessionPage(BaseModel):
    items: list[AdminSession]
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class SecurityOverview(BaseModel):
    activeSessions: int
    activeUsers: int
    expiringSoon: int
    revoked24h: int
    failedLogins24h: int
    deniedRequests24h: int


class RevokeSessionsRequest(BaseModel):
    excludeCurrent: bool = True
