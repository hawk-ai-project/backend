"""HTTP endpoints for signup, login, session lookup, and logout."""

from fastapi import APIRouter, Depends, File, Header, Response, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse

from domain.auth import AuthResponse, LoginRequest, MessageResponse, ProfileUpdateRequest, SignupRequest, UserResponse
from service import auth_service
from service import file_service


router = APIRouter(prefix="/api/auth", tags=["인증"])


def _bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise auth_service.AuthError("인증이 필요합니다.")
    return authorization[7:].strip()


def current_auth(token: str = Depends(_bearer_token)):
    return auth_service.authenticate(token)


@router.post("/signup", response_model=UserResponse, status_code=201)
def signup(payload: SignupRequest):
    return auth_service.signup(payload.name, str(payload.email), payload.password)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    return auth_service.login(str(payload.email), payload.password)


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
def logout(auth=Depends(current_auth)):
    auth_service.auth_repository.revoke_session(auth[1]["sid"])
    return {"message": "로그아웃되었습니다."}


def auth_error_response(_request, exc: auth_service.AuthError):
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})
