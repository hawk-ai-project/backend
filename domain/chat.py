from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


ChatIntent = Literal["FAQ", "INSPECTION_HISTORY", "PROJECT_INFO", "CASUAL_CHAT"]
ChatSourceType = Literal["STATIC_FAQ", "INSPECTION_DB", "PROJECT_INFO", "QWEN"]


class ChatHistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=500)

    @field_validator("content")
    @classmethod
    def require_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("대화 내용은 비어 있을 수 없습니다.")
        return value.strip()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)
    history: list[ChatHistoryMessage] = Field(default_factory=list, max_length=12)

    @field_validator("message")
    @classmethod
    def require_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("질문을 입력해 주세요.")
        return value.strip()

    @model_validator(mode="after")
    def exclude_current_message_from_history(self) -> "ChatRequest":
        if (
            self.history
            and self.history[-1].role == "user"
            and self.history[-1].content == self.message
        ):
            raise ValueError("현재 질문은 history가 아닌 message에만 포함해 주세요.")
        return self


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


class ChatNavigationAction(BaseModel):
    type: Literal["NAVIGATE"]
    path: Literal[
        "/inspection",
        "/histories",
        "/analytics",
        "/boards",
        "/boards/write",
        "/login",
    ]


class ChatResponse(BaseModel):
    answer: str
    type: ChatIntent
    sourceType: ChatSourceType
    sources: list[ChatSource] = Field(default_factory=list)
    actions: list[ChatAction] = Field(default_factory=list, max_length=2)
    intent: str | None = None
    action: ChatNavigationAction | None = None
