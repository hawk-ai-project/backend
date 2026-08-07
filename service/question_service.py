from fastapi import HTTPException

from domain.question import QuestionCreate, QuestionUpdate
from repository import question_repository


def get_question_list() -> list[dict]:
    return question_repository.find_all()


def get_question(question_id: int) -> dict:
    question = question_repository.find_by_id(question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    return question


def create_question(payload: QuestionCreate) -> dict:
    return get_question(question_repository.create(payload.subject, payload.content))


def update_question(question_id: int, payload: QuestionUpdate) -> dict:
    if question_repository.find_by_id(question_id) is None:
        raise HTTPException(status_code=404, detail="Question not found")
    question_repository.update(question_id, payload.subject, payload.content)
    return get_question(question_id)


def delete_question(question_id: int) -> None:
    if question_repository.delete(question_id) == 0:
        raise HTTPException(status_code=404, detail="Question not found")
