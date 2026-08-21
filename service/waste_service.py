"""폐기물 유형 비즈니스 로직 서비스."""
from fastapi import HTTPException
from domain.waste import WasteCreate, WasteUpdate
from repository import waste_repository

def get_all_wastes() -> list[dict]:
    return waste_repository.find_all()

def get_waste(waste_id: int) -> dict:
    waste = waste_repository.find_by_id(waste_id)
    if waste is None:
        raise HTTPException(status_code=404, detail="해당 폐기물 유형을 찾을 수 없습니다.")
    return waste

def create_waste(payload: WasteCreate) -> dict:
    new_id = waste_repository.create(payload)
    return get_waste(new_id)

def update_waste(waste_id: int, payload: WasteUpdate) -> dict:
    get_waste(waste_id)
    waste_repository.update(waste_id, payload)
    return get_waste(waste_id)

def delete_waste(waste_id: int) -> dict:
    """폐기물 유형 삭제 비즈니스 로직"""
    get_waste(waste_id)  # 존재 여부 검증
    waste_repository.delete(waste_id)
    return {"message": "성공적으로 삭제되었습니다.", "id": waste_id}