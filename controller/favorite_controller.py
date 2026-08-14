from fastapi import APIRouter, Depends, status, HTTPException
from typing import List
from domain.favorite import FavoriteCreate, FavoriteResponse
from service.favorite_service import FavoriteService, get_favorite_service
from controller.auth_controller import get_current_user_id

router = APIRouter(prefix="/api/favorites", tags=["Favorites"])

@router.get("/top5", response_model=List[FavoriteResponse])
def get_top5_favorites(
    current_user_id: int = Depends(get_current_user_id),
    service: FavoriteService = Depends(get_favorite_service)
):
    return service.get_top5_favorites(current_user_id)


@router.post("/{favorite_id}/click", status_code=status.HTTP_200_OK)
def record_click(
    favorite_id: int,
    current_user_id: int = Depends(get_current_user_id),
    service: FavoriteService = Depends(get_favorite_service)
):
    success = service.record_favorite_click(favorite_id, current_user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Favorite item not found")
    return {"status": "success"}


@router.post("", status_code=status.HTTP_201_CREATED)
def add_favorite(
    item: FavoriteCreate,
    current_user_id: int = Depends(get_current_user_id),
    service: FavoriteService = Depends(get_favorite_service)
):
    service.add_or_update_favorite(current_user_id, item)
    return {"status": "success"}


@router.delete("/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_favorite(
    favorite_id: int,
    current_user_id: int = Depends(get_current_user_id),
    service: FavoriteService = Depends(get_favorite_service)
):
    service.remove_favorite(favorite_id, current_user_id)