"""게시판 도메인 모델."""

from datetime import datetime

from pydantic import BaseModel


class BoardAuthor(BaseModel):
    id: int
    name: str


class Board(BaseModel):
    id: int
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
