"""Response models for administrator APIs."""

from datetime import datetime

from pydantic import BaseModel


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
