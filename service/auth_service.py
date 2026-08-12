"""Password hashing and signed access-token authentication."""

import base64
import hashlib
import hmac
import json
import os
import uuid
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from config import settings
from repository import auth_repository, file_repository
from repository import settings_repository
from service import file_service


class AuthError(Exception):
    def __init__(self, message: str, status_code: int = 401):
        self.message = message
        self.status_code = status_code


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    iterations = 600_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_b64encode(salt)}${_b64encode(digest)}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, iterations, salt, expected = encoded.split("$", 3)
        if scheme != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), _b64decode(salt), int(iterations)
        )
        return hmac.compare_digest(actual, _b64decode(expected))
    except (ValueError, TypeError):
        return False


def _encode_token(user_id: int, session_id: str, expires_at: datetime) -> str:
    if settings.algorithm != "HS256":
        raise RuntimeError("Only the HS256 token algorithm is supported")
    header = _b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64encode(json.dumps({
        "sub": str(user_id), "sid": session_id,
        "iat": int(datetime.now(timezone.utc).timestamp()),
        "exp": int(expires_at.timestamp()),
    }, separators=(",", ":")).encode())
    unsigned = f"{header}.{payload}"
    signature = hmac.new(settings.secret_key.encode(), unsigned.encode(), hashlib.sha256).digest()
    return f"{unsigned}.{_b64encode(signature)}"


def _new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _access_token_lifetime(session_minutes: int) -> timedelta:
    """Keep the access token shorter than the renewable server session."""
    minutes = min(settings.access_token_expire_minutes, max(1, session_minutes // 2))
    return timedelta(minutes=minutes)


def decode_token(token: str) -> dict[str, Any]:
    try:
        header, payload, signature = token.split(".")
        unsigned = f"{header}.{payload}"
        expected = hmac.new(settings.secret_key.encode(), unsigned.encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            raise ValueError
        claims = json.loads(_b64decode(payload))
        if int(claims["exp"]) <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError
        int(claims["sub"])
        uuid.UUID(claims["sid"])
        return claims
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise AuthError("유효하지 않거나 만료된 인증 정보입니다.") from None


def _public_user(user: dict[str, Any]) -> dict[str, Any]:
    result = {key: user[key] for key in ("id", "name", "email", "role")}
    result["profileFileId"] = user.get("profileFileId")
    result["profileImageUrl"] = (
        "/api/auth/profile/image" if user.get("profileFileId") else None
    )
    return result


def signup(name: str, email: str, password: str) -> dict[str, Any]:
    if settings_repository.get_value("signup_enabled", "true") != "true":
        raise AuthError("현재 신규 회원가입이 중지되어 있습니다.", 403)
    normalized_email = email.strip().lower()
    clean_name = name.strip()
    if not clean_name:
        raise AuthError("이름을 입력해 주세요.", 422)
    if auth_repository.find_user_by_email(normalized_email):
        raise AuthError("이미 가입된 이메일입니다.", 409)
    try:
        user_id = auth_repository.create_user(clean_name, normalized_email, _hash_password(password))
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise AuthError("이미 가입된 이메일입니다.", 409) from None
        raise
    user = auth_repository.find_user_by_id(user_id)
    if not user:
        raise AuthError("회원가입 처리 중 오류가 발생했습니다.", 500)
    return _public_user(user)


def login(
    email: str,
    password: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    user = auth_repository.find_user_by_email(email.strip().lower())
    if not user or not _verify_password(password, user["password_hash"]):
        raise AuthError("이메일 또는 비밀번호가 올바르지 않습니다.")
    if user["status"] != "ACTIVE":
        raise AuthError("사용할 수 없는 계정입니다.", 403)
    session_id = str(uuid.uuid4())
    expire_minutes = int(settings_repository.get_value(
        "session_expire_minutes", str(settings.access_token_expire_minutes)
    ))
    now = datetime.now(timezone.utc)
    access_expires_at = now + _access_token_lifetime(expire_minutes)
    session_expires_at = now + timedelta(minutes=expire_minutes)
    refresh_token = _new_refresh_token()
    auth_repository.create_session(
        session_id, user["id"], session_expires_at.replace(tzinfo=None),
        user_agent[:500] if user_agent else None,
        ip_address[:45] if ip_address else None,
        _hash_refresh_token(refresh_token),
    )
    auth_repository.touch_login(user["id"], session_id)
    return {
        "accessToken": _encode_token(user["id"], session_id, access_expires_at),
        "refreshToken": refresh_token,
        "refreshMaxAge": expire_minutes * 60,
        "user": _public_user(user),
    }


def refresh(
    refresh_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    next_token = _new_refresh_token()
    session_minutes = int(settings_repository.get_value(
        "session_expire_minutes", str(settings.access_token_expire_minutes)
    ))
    now = datetime.now(timezone.utc)
    session = auth_repository.rotate_refresh_token(
        _hash_refresh_token(refresh_token), _hash_refresh_token(next_token),
        (now + timedelta(minutes=session_minutes)).replace(tzinfo=None),
        user_agent[:500] if user_agent else None,
        ip_address[:45] if ip_address else None,
    )
    if not session:
        raise AuthError("로그인이 만료되었습니다.")
    user = auth_repository.find_user_by_id(int(session["userId"]))
    if not user or user["status"] != "ACTIVE":
        auth_repository.revoke_session(session["id"])
        raise AuthError("사용할 수 없는 계정입니다.", 403)
    access_expires_at = now + _access_token_lifetime(session_minutes)
    return {
        "accessToken": _encode_token(user["id"], session["id"], access_expires_at),
        "refreshToken": next_token,
        "refreshMaxAge": session_minutes * 60,
        "user": _public_user(user),
    }


def revoke_refresh_token(refresh_token: str | None) -> None:
    if refresh_token:
        auth_repository.revoke_by_refresh_hash(_hash_refresh_token(refresh_token))


def authenticate(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    claims = decode_token(token)
    user_id = int(claims["sub"])
    if not auth_repository.find_active_session(claims["sid"], user_id):
        raise AuthError("로그인이 만료되었습니다.")
    user = auth_repository.find_user_by_id(user_id)
    if not user or user["status"] != "ACTIVE":
        raise AuthError("사용할 수 없는 계정입니다.", 403)
    return _public_user(user), claims


def update_profile(
    user_id: int,
    name: str,
    email: str,
    current_password: str | None,
    new_password: str | None,
) -> dict[str, Any]:
    clean_name = name.strip()
    normalized_email = email.strip().lower()
    if not clean_name:
        raise AuthError("이름을 입력해 주세요.", 422)

    existing_email_user = auth_repository.find_user_by_email(normalized_email)
    if existing_email_user and existing_email_user["id"] != user_id:
        raise AuthError("이미 사용 중인 이메일입니다.", 409)

    password_hash = None
    if new_password:
        current_user = auth_repository.find_user_credentials_by_id(user_id)
        if not current_password or not current_user or not _verify_password(current_password, current_user["password_hash"]):
            raise AuthError("현재 비밀번호가 올바르지 않습니다.", 400)
        password_hash = _hash_password(new_password)

    try:
        auth_repository.update_profile(user_id, clean_name, normalized_email, password_hash)
    except Exception as exc:
        if "duplicate" in str(exc).lower():
            raise AuthError("이미 사용 중인 이메일입니다.", 409) from None
        raise
    updated = auth_repository.find_user_by_id(user_id)
    if not updated:
        raise AuthError("사용자 정보를 찾을 수 없습니다.", 404)
    return _public_user(updated)


def update_profile_image(file, user: dict[str, Any]) -> dict[str, Any]:
    uploaded = file_service.upload_profile_image(file, user["id"])
    previous_file_id = user.get("profileFileId")
    try:
        auth_repository.set_profile_file(user["id"], uploaded["fileId"])
    except Exception:
        file_service.delete(uploaded["objectKey"], user["id"])
        raise

    if previous_file_id:
        previous = file_repository.find_by_id_owned(previous_file_id, user["id"])
        if previous:
            try:
                file_service.delete(previous["object_key"], user["id"])
            except Exception:
                pass

    updated = auth_repository.find_user_by_id(user["id"])
    if not updated:
        raise AuthError("User not found.", 404)
    return _public_user(updated)


def remove_profile_image(user: dict[str, Any]) -> dict[str, Any]:
    profile_file_id = user.get("profileFileId")
    if profile_file_id:
        stored = file_repository.find_by_id_owned(profile_file_id, user["id"])
        auth_repository.set_profile_file(user["id"], None)
        if stored:
            try:
                file_service.delete(stored["object_key"], user["id"])
            except Exception:
                pass
    updated = auth_repository.find_user_by_id(user["id"])
    if not updated:
        raise AuthError("User not found.", 404)
    return _public_user(updated)
