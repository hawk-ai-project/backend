from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


ChatIntent = Literal["FAQ", "INSPECTION_HISTORY", "PROJECT_INFO"]
ChatSourceType = Literal["STATIC_FAQ", "INSPECTION_DB", "PROJECT_INFO", "QWEN"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def require_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("질문을 입력해 주세요.")
        return value.strip()


class ChatSource(BaseModel):
    id: int
    location: str
    capturedAt: datetime


class ChatAction(BaseModel):
    label: str
    href: str

    @field_validator("href")
    @classmethod
    def require_internal_path(cls, value: str) -> str:
        if not value.startswith("/") or value.startswith("//"):
            raise ValueError("내부 상대 경로만 사용할 수 있습니다.")
        return value


class ChatResponse(BaseModel):
    answer: str
    type: ChatIntent
    sourceType: ChatSourceType
    sources: list[ChatSource] = Field(default_factory=list)
    actions: list[ChatAction] = Field(default_factory=list, max_length=2)
