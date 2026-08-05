# domain/question/question_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
import crud
import schemas

router = APIRouter(
    prefix="/api/question",
    tags=["question"]
)

# 1. 목록 조회
@router.get("/list", response_model=List[schemas.Question])
def question_list(db: Session = Depends(get_db)):
    return crud.get_question_list(db)

# 2. 상세 조회
@router.get("/detail/{question_id}", response_model=schemas.Question)
def question_detail(question_id: int, db: Session = Depends(get_db)):
    question = crud.get_question(db, question_id=question_id)
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")
    return question

# 3. 등록
@router.post("/create", response_model=schemas.Question)
def question_create(question_create: schemas.QuestionCreate, db: Session = Depends(get_db)):
    return crud.create_question(db=db, question_create=question_create)

# 4. 수정
@router.put("/update/{question_id}", response_model=schemas.Question)
def question_update(question_id: int, question_update: schemas.QuestionUpdate, db: Session = Depends(get_db)):
    updated_question = crud.update_question(db=db, question_id=question_id, question_update=question_update)
    if not updated_question:
        raise HTTPException(status_code=404, detail="Question not found")
    return updated_question

# 5. 삭제
@router.delete("/delete/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def question_delete(question_id: int, db: Session = Depends(get_db)):
    success = crud.delete_question(db=db, question_id=question_id)
    if not success:
        raise HTTPException(status_code=404, detail="Question not found")
    return None