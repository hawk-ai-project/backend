"""질문 도메인 모델."""

from datetime import datetime

from pydantic import BaseModel


class QuestionCreate(BaseModel):
    subject: str
    content: str


class QuestionUpdate(BaseModel):
    subject: str
    content: str


class Question(BaseModel):
    id: int
    subject: str
    content: str
    create_date: datetime
