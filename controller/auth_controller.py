"""HTTP endpoints for signup, login, session lookup, and logout."""

from fastapi import APIRouter, Depends, Header
from fastapi.responses import JSONResponse

from domain.auth import AuthResponse, LoginRequest, MessageResponse, SignupRequest, UserResponse
from service import auth_service


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


@router.post("/logout", response_model=MessageResponse)
def logout(auth=Depends(current_auth)):
    auth_service.auth_repository.revoke_session(auth[1]["sid"])
    return {"message": "로그아웃되었습니다."}


def auth_error_response(_request, exc: auth_service.AuthError):
    return JSONResponse(status_code=exc.status_code, content={"message": exc.message})
