# backend/service/waste_type_service.py

from repository import waste_type_repository

def get_waste_types():
    return waste_type_repository.get_all_waste_types()