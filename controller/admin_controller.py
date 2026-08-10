"""Administrator-only HTTP endpoints."""

from fastapi import APIRouter, Depends, Query

from controller.auth_controller import current_auth
from domain.admin import AdminUserPage, DashboardStats
from service import admin_service


router = APIRouter(prefix="/api/admin", tags=["관리자"])


def current_admin(auth=Depends(current_auth)):
    return admin_service.require_admin(auth)


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(_admin=Depends(current_admin)):
    return admin_service.get_dashboard()


@router.get("/users", response_model=AdminUserPage)
def users(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=100),
    _admin=Depends(current_admin),
):
    return admin_service.get_users(page, pageSize, keyword.strip() if keyword else None)
