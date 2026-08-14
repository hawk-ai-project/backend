"""HTTP endpoints for signup, login, session lookup, and logout."""

from fastapi import APIRouter, Cookie, Depends, File, Header, Request, Response, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse

from domain.auth import AuthResponse, LoginRequest, MessageResponse, ProfileUpdateRequest, SignupRequest, UserResponse
from service import auth_service
from service import file_service


router = APIRouter(prefix="/api/auth", tags=["인증"])
REFRESH_COOKIE = "hawk_ai_refresh_token"


def _request_is_https(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    effective_scheme = forwarded_proto.split(",", 1)[0].strip().lower() or request.url.scheme
    return effective_scheme == "https"


def _set_refresh_cookie(request: Request, response: Response, token: str, max_age: int) -> None:
    # Secure cookies are required on HTTPS, but browsers discard them when the
    # development UI calls an HTTP API directly. Keep the configured security
    # preference while allowing the local/LAN HTTP environment to refresh.
    secure = auth_service.settings.refresh_cookie_secure and _request_is_https(request)
    response.set_cookie(
        key=REFRESH_COOKIE, value=token, max_age=max_age,
        httponly=True, secure=secure,
        samesite="lax", path="/api/auth",
    )


def _bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise auth_service.AuthError("인증이 필요합니다.")
    return authorization[7:].strip()


def current_auth(request: Request, token: str = Depends(_bearer_token)):
    auth = auth_service.authenticate(token)
    request.state.activity_user_id = auth[0]["id"]
    request.state.activity_session_id = auth[1]["sid"]
    return auth


@router.post("/signup", response_model=UserResponse, status_code=201)
def signup(payload: SignupRequest, request: Request):
    user = auth_service.signup(payload.name, str(payload.email), payload.password)
    request.state.activity_user_id = user["id"]
    return user


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, request: Request, response: Response):
    result = auth_service.login(
        str(payload.email), payload.password,
        request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )
    request.state.activity_user_id = result["user"]["id"]
    request.state.activity_session_id = auth_service.decode_token(result["accessToken"])["sid"]
    _set_refresh_cookie(request, response, result.pop("refreshToken"), result.pop("refreshMaxAge"))
    return result


@router.post("/refresh", response_model=AuthResponse)
def refresh_session(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
):
    if not refresh_token:
        raise auth_service.AuthError("로그인이 만료되었습니다.")
    result = auth_service.refresh(
        refresh_token, request.headers.get("user-agent"),
        request.client.host if request.client else None,
    )
    request.state.activity_user_id = result["user"]["id"]
    request.state.activity_session_id = auth_service.decode_token(result["accessToken"])["sid"]
    _set_refresh_cookie(request, response, result.pop("refreshToken"), result.pop("refreshMaxAge"))
    return result


@router.get("/me", response_model=UserResponse)
def me(auth=Depends(current_auth)):
    return auth[0]


@router.patch("/profile", response_model=UserResponse)
def update_profile(payload: ProfileUpdateRequest, auth=Depends(current_auth)):
    return auth_service.update_profile(
        auth[0]["id"], payload.name, payload.email,
        payload.currentPassword, payload.newPassword,
    )


@router.patch("/profile/image", response_model=UserResponse)
def update_profile_image(
    file: UploadFile = File(...),
    auth=Depends(current_auth),
):
    try:
        return auth_service.update_profile_image(file, auth[0])
    finally:
        file.file.close()


@router.get("/profile/image")
def get_profile_image(auth=Depends(current_auth)):
    file_id = auth[0].get("profileFileId")
    if not file_id:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    stored_file = file_service.open_by_id(file_id, auth[0]["id"])

    def stream():
        try:
            yield from stored_file.stream(32 * 1024)
        finally:
            stored_file.close()
            stored_file.release_conn()

    content_type = stored_file.headers.get("Content-Type", "application/octet-stream")
    return StreamingResponse(stream(), media_type=content_type)


@router.delete("/profile/image", response_model=UserResponse)
def delete_profile_image(auth=Depends(current_auth)):
    return auth_service.remove_profile_image(auth[0])


@router.post("/logout", response_model=MessageResponse)
def logout(
    response: Response,
    authorization: str | None = Header(default=None),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
):
    if authorization and authorization.startswith("Bearer "):
        try:
            claims = auth_service.decode_token(authorization[7:].strip())
            auth_service.auth_repository.revoke_session(claims["sid"])
        except auth_service.AuthError:
            pass
    auth_service.revoke_refresh_token(refresh_token)
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")
    return {"message": "로그아웃되었습니다."}


def auth_error_response(_request, exc: auth_service.AuthError):
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})

def get_current_user_id(auth=Depends(current_auth)) -> int:
    """인증된 유저의 ID(pk)만 반환하는 의존성 함수"""
    return auth[0]["id"]
