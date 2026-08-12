"""Administrator-only HTTP endpoints."""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse

from controller.auth_controller import current_auth
from domain.admin import (
    ActivityLogPage, ActivityOverview, AdminBoardPage, AdminRole, AdminSessionPage,
    AdminUserPage, BoardStatusUpdateRequest, DashboardStats, RevokeSessionsRequest,
    RoleUpdateRequest, SecurityOverview,
)
from domain.auth import UserResponse
from domain.settings import ServiceSettings
from domain.monitoring import MonitoringOverview, MonitoringSettings
from service import admin_service
from service import activity_service
from service import monitoring_service


router = APIRouter(prefix="/api/admin", tags=["관리자"])


def current_admin(auth=Depends(current_auth)):
    return admin_service.require_admin(auth)


@router.get("/dashboard", response_model=DashboardStats)
def dashboard(_admin=Depends(current_admin)):
    return admin_service.get_dashboard()


@router.get("/security/overview", response_model=SecurityOverview)
def security_overview(_admin=Depends(current_admin)):
    return admin_service.get_security_overview()


@router.get("/security/sessions", response_model=AdminSessionPage)
def security_sessions(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=100),
    sessionStatus: str | None = Query(default=None, alias="status", pattern="^(ACTIVE|EXPIRED|REVOKED)$"),
    _admin=Depends(current_admin),
):
    return admin_service.get_sessions(
        page, pageSize, keyword.strip() if keyword else None, sessionStatus,
    )


@router.delete("/security/sessions/{session_id}")
def revoke_security_session(session_id: str, auth=Depends(current_auth)):
    admin_service.require_admin(auth)
    return admin_service.revoke_session(session_id, auth[1]["sid"])


@router.post("/security/sessions/revoke-all")
def revoke_all_security_sessions(
    payload: RevokeSessionsRequest,
    auth=Depends(current_auth),
):
    admin_service.require_admin(auth)
    return admin_service.revoke_all_sessions(auth[1]["sid"], payload.excludeCurrent)


@router.get("/activity/overview", response_model=ActivityOverview)
def activity_overview(
    hours: int = Query(default=24, ge=1, le=168),
    _admin=Depends(current_admin),
):
    return activity_service.get_overview(hours)


@router.get("/activity", response_model=ActivityLogPage)
def activity_logs(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=30, ge=1, le=100),
    fromAt: datetime | None = Query(default=None, alias="from"),
    toAt: datetime | None = Query(default=None, alias="to"),
    category: str | None = Query(default=None, max_length=30, pattern="^[A-Z_]+$"),
    outcome: str | None = Query(default=None, pattern="^(SUCCESS|DENIED|FAILURE)$"),
    userId: int | None = Query(default=None, ge=1),
    keyword: str | None = Query(default=None, max_length=100),
    _admin=Depends(current_admin),
):
    return activity_service.get_logs(
        page, pageSize, fromAt, toAt, category, outcome, userId,
        keyword.strip() if keyword else None,
    )


@router.get("/monitoring/overview", response_model=MonitoringOverview)
def monitoring_overview(_admin=Depends(current_admin)):
    return monitoring_service.get_overview()


@router.get("/monitoring/settings", response_model=MonitoringSettings)
def monitoring_settings(_admin=Depends(current_admin)):
    return monitoring_service.get_settings()


@router.put("/monitoring/settings", response_model=MonitoringSettings)
def update_monitoring_settings(
    payload: MonitoringSettings,
    admin=Depends(current_admin),
):
    return monitoring_service.save_settings(payload, admin["id"])


@router.get("/boards", response_model=AdminBoardPage)
def boards(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=100),
    statusFilter: str | None = Query(default=None, alias="status", pattern="^(DRAFT|PUBLISHED|HIDDEN)$"),
    _admin=Depends(current_admin),
):
    return admin_service.get_boards(
        page, pageSize, keyword.strip() if keyword else None, statusFilter
    )


@router.patch("/boards/{board_id}/status")
def update_board_status(
    board_id: int,
    payload: BoardStatusUpdateRequest,
    _admin=Depends(current_admin),
):
    return admin_service.change_board_status(board_id, payload.status)


@router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(board_id: int, _admin=Depends(current_admin)):
    admin_service.delete_board(board_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

@router.get("/users", response_model=AdminUserPage)
def users(
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    keyword: str | None = Query(default=None, max_length=100),
    _admin=Depends(current_admin),
):
    return admin_service.get_users(page, pageSize, keyword.strip() if keyword else None)


@router.get("/roles", response_model=list[AdminRole])
def roles(_admin=Depends(current_admin)):
    return admin_service.get_roles()


@router.get("/users/{user_id}/profile-image")
def user_profile_image(user_id: int, _admin=Depends(current_admin)):
    stored_file = admin_service.get_user_profile_image(user_id)

    def stream():
        try:
            yield from stored_file.stream(32 * 1024)
        finally:
            stored_file.close()
            stored_file.release_conn()

    content_type = stored_file.headers.get("Content-Type", "application/octet-stream")
    return StreamingResponse(stream(), media_type=content_type)


@router.patch("/users/{user_id}/role", response_model=UserResponse)
def update_role(user_id: int, payload: RoleUpdateRequest, admin=Depends(current_admin)):
    return admin_service.change_user_role(admin, user_id, payload.roleCode)


@router.get("/settings", response_model=ServiceSettings)
def get_settings(_admin=Depends(current_admin)):
    return admin_service.get_service_settings()


@router.put("/settings", response_model=ServiceSettings)
def update_settings(payload: ServiceSettings, admin=Depends(current_admin)):
    return admin_service.update_service_settings(admin, payload)
