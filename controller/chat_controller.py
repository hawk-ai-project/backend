from fastapi import APIRouter, Header

from domain.chat import ChatRequest, ChatResponse
from service import auth_service, chat_service


router = APIRouter(prefix="/api/chat", tags=["챗봇"])


def _optional_user(authorization: str | None) -> dict | None:
    if not authorization:
        return None
    if not authorization.startswith("Bearer "):
        raise auth_service.AuthError("올바른 인증 정보가 필요합니다.")
    return auth_service.authenticate(authorization[7:].strip())[0]


@router.post("", response_model=ChatResponse)
def chat(payload: ChatRequest, authorization: str | None = Header(default=None)):
    return chat_service.chat(payload.message, _optional_user(authorization))
