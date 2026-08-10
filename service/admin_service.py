"""Administrator authorization and dashboard operations."""

import math

from repository import admin_repository
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
