from fastapi import APIRouter
from domain.waste import WasteCreate, WasteUpdate
from service import waste_service

router = APIRouter(prefix="/api/wastes", tags=["waste"])

@router.get("")
def get_all_wastes():
    return waste_service.get_all_wastes()

@router.get("/{waste_id}")
def get_waste_detail(waste_id: int):
    return waste_service.get_waste(waste_id)

@router.post("")
def create_waste(payload: WasteCreate):
    return waste_service.create_waste(payload)

@router.patch("/{waste_id}")
def update_waste(waste_id: int, payload: WasteUpdate):
    return waste_service.update_waste(waste_id, payload)

@router.delete("/{waste_id}")
def delete_waste(waste_id: int):
    """폐기물 유형 삭제 API"""
    return waste_service.delete_waste(waste_id)