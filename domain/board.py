"""게시판 도메인 모델."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class BoardAuthor(BaseModel):
    id: int
    name: str


class Board(BaseModel):
    id: int
    categoryId: int
    category: str
    title: str
    summary: str | None
    content: str
    tags: list[str]
    author: BoardAuthor
    createdAt: datetime
    updatedAt: datetime
    viewCount: int
    thumbnailUrl: str | None


class BoardPage(BaseModel):
    items: list[Board]
    page: int
    pageSize: int
    totalItems: int
    totalPages: int


class BoardCreate(BaseModel):
    categoryId: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=100)
    summary: str | None = Field(default=None, max_length=500)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list, max_length=8)

    @field_validator("title", "content")
    @classmethod
    def require_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("빈 값은 입력할 수 없습니다.")
        return value.strip()

    @field_validator("summary")
    @classmethod
    def normalize_summary(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        normalized: set[str] = set()
        for value in values:
            tag = value.strip().lstrip("#").strip()
            key = "".join(tag.lower().split())
            if not tag or len(tag) > 20:
                raise ValueError("태그는 1자 이상 20자 이하로 입력해 주세요.")
            if key not in normalized:
                normalized.add(key)
                result.append(tag)
        return result


class BoardUpdate(BaseModel):
    categoryId: int | None = Field(default=None, gt=0)
    title: str | None = Field(default=None, min_length=1, max_length=100)
    summary: str | None = Field(default=None, max_length=500)
    content: str | None = Field(default=None, min_length=1)
    tags: list[str] | None = Field(default=None, max_length=8)

    @field_validator("title", "content")
    @classmethod
    def require_non_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("빈 값은 입력할 수 없습니다.")
        return value.strip() if value is not None else None

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, values: list[str] | None) -> list[str] | None:
        return BoardCreate.validate_tags(values) if values is not None else None
