from fastapi import APIRouter, status

from domain.question import Question, QuestionCreate, QuestionUpdate
from service import question_service


router = APIRouter(prefix="/api/question", tags=["question"])


@router.get("/list", response_model=list[Question])
def question_list():
    return question_service.get_question_list()


@router.get("/detail/{question_id}", response_model=Question)
def question_detail(question_id: int):
    return question_service.get_question(question_id)


@router.post("/create", response_model=Question)
def question_create(payload: QuestionCreate):
    return question_service.create_question(payload)


@router.put("/update/{question_id}", response_model=Question)
def question_update(question_id: int, payload: QuestionUpdate):
    return question_service.update_question(question_id, payload)


@router.delete("/delete/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def question_delete(question_id: int):
    question_service.delete_question(question_id)
    return None
