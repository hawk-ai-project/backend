"""Administrator authorization and dashboard operations."""

import math

from repository import admin_repository
from repository import settings_repository
from service.auth_service import AuthError


def require_admin(auth):
    user, _claims = auth
    if user.get("role") != "ADMIN":
        raise AuthError("관리자 권한이 필요합니다.", 403)
    return user


def get_users(page: int, page_size: int, keyword: str | None):
    items, total = admin_repository.find_users(page, page_size, keyword)
    return {
        "items": items,
        "page": page,
        "pageSize": page_size,
        "totalItems": total,
        "totalPages": math.ceil(total / page_size) if total else 0,
    }


def get_dashboard():
    return {**admin_repository.dashboard_stats(), "recentUsers": admin_repository.recent_users()}


def get_roles():
    return admin_repository.find_roles()


def get_user_profile_image(user_id: int):
    from repository import auth_repository
    from service import file_service

    user = auth_repository.find_user_by_id(user_id)
    if not user:
        raise AuthError("User not found.", 404)
    file_id = user.get("profileFileId")
    if not file_id:
        raise AuthError("Profile image not found.", 404)
    return file_service.open_by_id(file_id, user_id)


def change_user_role(admin: dict, user_id: int, role_code: str):
    if admin["id"] == user_id:
        raise AuthError("현재 로그인한 계정의 권한은 직접 변경할 수 없습니다.", 400)
    # Fetch the exact target independently from pagination ordering.
    from repository import auth_repository
    target_user = auth_repository.find_user_by_id(user_id)
    if not target_user:
        raise AuthError("회원을 찾을 수 없습니다.", 404)
    roles = {role["code"] for role in admin_repository.find_roles()}
    if role_code not in roles:
        raise AuthError("존재하지 않는 권한입니다.", 422)
    if target_user["role"] == "ADMIN" and role_code != "ADMIN" and admin_repository.count_admins() <= 1:
        raise AuthError("최소 한 명의 활성 관리자가 필요합니다.", 409)
    if target_user["role"] != role_code and not admin_repository.update_user_role(user_id, role_code):
        raise AuthError("권한을 변경하지 못했습니다.", 500)
    updated = auth_repository.find_user_by_id(user_id)
    return updated


def get_service_settings():
    values = settings_repository.get_all()
    return {
        "signupEnabled": values["signup_enabled"] == "true",
        "boardWriteEnabled": values["board_write_enabled"] == "true",
        "inspectionNotificationEnabled": values["inspection_notification_enabled"] == "true",
        "sessionExpireMinutes": int(values["session_expire_minutes"]),
    }


def update_service_settings(admin: dict, payload):
    settings_repository.save_all({
        "signup_enabled": payload.signupEnabled,
        "board_write_enabled": payload.boardWriteEnabled,
        "inspection_notification_enabled": payload.inspectionNotificationEnabled,
        "session_expire_minutes": payload.sessionExpireMinutes,
    }, admin["id"])
    return get_service_settings()


def get_boards(page: int, page_size: int, keyword: str | None, status: str | None):
    items, total = admin_repository.find_boards(page, page_size, keyword, status)
    return {
        "items": items,
        "page": page,
        "pageSize": page_size,
        "totalItems": total,
        "totalPages": math.ceil(total / page_size) if total else 0,
    }


def change_board_status(board_id: int, status: str):
    if not admin_repository.update_board_status(board_id, status):
        raise AuthError("게시글을 찾을 수 없습니다.", 404)
    return {"id": board_id, "status": status}


def delete_board(board_id: int) -> None:
    if not admin_repository.soft_delete_board(board_id):
        raise AuthError("게시글을 찾을 수 없습니다.", 404)


def get_security_overview():
    return admin_repository.security_overview()


def get_sessions(page: int, page_size: int, keyword: str | None, session_status: str | None):
    items, total = admin_repository.find_sessions(page, page_size, keyword, session_status)
    return {
        "items": items, "page": page, "pageSize": page_size, "totalItems": total,
        "totalPages": math.ceil(total / page_size) if total else 0,
    }


def revoke_session(session_id: str, current_session_id: str):
    if session_id == current_session_id:
        raise AuthError("현재 사용 중인 세션은 이 화면에서 종료할 수 없습니다.", 409)
    if not admin_repository.revoke_session_by_id(session_id):
        raise AuthError("활성 세션을 찾을 수 없습니다.", 404)
    return {"message": "세션이 종료되었습니다."}


def revoke_all_sessions(current_session_id: str, exclude_current: bool):
    count = admin_repository.revoke_all_sessions(current_session_id if exclude_current else None)
    return {"message": f"활성 세션 {count}개를 종료했습니다.", "revokedCount": count}
