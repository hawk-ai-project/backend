# backend/controller/waste_type_controller.py

from fastapi import APIRouter, Depends
from typing import List
from controller.auth_controller import current_auth
from domain.waste_type import WasteTypeResponse
from service import waste_type_service

router = APIRouter(prefix="/api/waste_types", tags=["폐기물 종류"])

@router.get("", response_model=List[WasteTypeResponse])
def get_waste_types(auth=Depends(current_auth)):
    return waste_type_service.get_waste_types()