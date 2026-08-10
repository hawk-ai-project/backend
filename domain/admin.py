"""Response models for administrator APIs."""

from datetime import datetime

from pydantic import BaseModel, Field


class AdminUser(BaseModel):
    id: int
    name: str
    email: str
    role: str
    status: str
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
