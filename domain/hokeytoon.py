from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator


class HokeytoonCommentAuthor(BaseModel):
    id: int
    name: str
    profileImageUrl: str | None = None


class HokeytoonComment(BaseModel):
    id: int
    episodeId: int
    parentId: int | None = None
    content: str
    emoticon: str | None = None
    author: HokeytoonCommentAuthor
    createdAt: datetime
    updatedAt: datetime
    replies: list["HokeytoonComment"] = Field(default_factory=list)


class HokeytoonCommentCreate(BaseModel):
    content: str = Field(default="", max_length=1000)
    parentId: int | None = Field(default=None, gt=0)
    emoticon: str | None = Field(default=None, pattern=r"^[a-z0-9_-]{1,40}$")

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def require_body(self):
        if not self.content and not self.emoticon:
            raise ValueError("댓글 내용이나 이모티콘을 입력해 주세요.")
        return self


class HokeytoonCommentUpdate(HokeytoonCommentCreate):
    parentId: None = None
