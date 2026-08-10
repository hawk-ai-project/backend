"""Password hashing and signed access-token authentication."""

import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from config import settings
from repository import auth_repository


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
    return {key: user[key] for key in ("id", "name", "email", "role")}


def signup(name: str, email: str, password: str) -> dict[str, Any]:
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


def login(email: str, password: str) -> dict[str, Any]:
    user = auth_repository.find_user_by_email(email.strip().lower())
    if not user or not _verify_password(password, user["password_hash"]):
        raise AuthError("이메일 또는 비밀번호가 올바르지 않습니다.")
    if user["status"] != "ACTIVE":
        raise AuthError("사용할 수 없는 계정입니다.", 403)
    session_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    auth_repository.create_session(session_id, user["id"], expires_at.replace(tzinfo=None))
    auth_repository.touch_login(user["id"], session_id)
    return {"accessToken": _encode_token(user["id"], session_id, expires_at), "user": _public_user(user)}


def authenticate(token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    claims = decode_token(token)
    user_id = int(claims["sub"])
    if not auth_repository.find_active_session(claims["sid"], user_id):
        raise AuthError("로그인이 만료되었습니다.")
    user = auth_repository.find_user_by_id(user_id)
    if not user or user["status"] != "ACTIVE":
        raise AuthError("사용할 수 없는 계정입니다.", 403)
    return _public_user(user), claims
