# crud.py
from sqlalchemy.orm import Session
from datetime import datetime
import models
import schemas

# 1. 질문 목록 조회
def get_question_list(db: Session):
    return db.query(models.Question).order_by(models.Question.create_date.desc()).all()

# 2. 질문 단건 조회
def get_question(db: Session, question_id: int):
    return db.query(models.Question).filter(models.Question.id == question_id).first()

# 3. 질문 등록 (Create)
def create_question(db: Session, question_create: schemas.QuestionCreate):
    db_question = models.Question(
        subject=question_create.subject,
        content=question_create.content,
        create_date=datetime.now()
    )
    db.add(db_question)
    db.commit()        # DB 반영
    db.refresh(db_question)  # 생성된 id값 받아오기
    return db_question

# 4. 질문 수정 (Update)
def update_question(db: Session, question_id: int, question_update: schemas.QuestionUpdate):
    db_question = get_question(db, question_id)
    if db_question:
        db_question.subject = question_update.subject
        db_question.content = question_update.content
        db.commit()
        db.refresh(db_question)
        return db_question
    return None

# 5. 질문 삭제 (Delete)
def delete_question(db: Session, question_id: int):
    db_question = get_question(db, question_id)
    if db_question:
        db.delete(db_question)
        db.commit()
        return True
    return False

# -------------------------------------------------------------
# [부유물 탐지 이력 CRUD 예시]
# 6. 탐지 결과 DB 저장
def create_detection_log(db: Session, log_create: schemas.DetectionLogCreate):
    db_log = models.DetectionLog(**log_create.model_dump())
    db.add(db_log)
    db.commit()
    db.refresh(db_log)
    return db_log