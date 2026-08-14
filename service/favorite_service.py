from typing import List
from domain.favorite import FavoriteCreate, FavoriteResponse
from repository import favorite_repository


class FavoriteService:
    def get_top5_favorites(self, user_id: int) -> List[FavoriteResponse]:
        rows = favorite_repository.find_top5_by_user_id(user_id)
        return [FavoriteResponse(**row) if isinstance(row, dict) else row for row in rows]

    def record_favorite_click(self, favorite_id: int, user_id: int) -> bool:
        return favorite_repository.increment_visit_count(favorite_id, user_id)

    def add_or_update_favorite(self, user_id: int, item: FavoriteCreate) -> bool:
        # 1. URL 정규화 (끝에 붙은 / 제거)
        clean_path = item.path.rstrip('/') if item.path else ''
        if not clean_path:
            clean_path = '/'

        # 2. 메인/루트 경로('/')는 즐겨찾기 저장에서 제외
        if clean_path == '/':
            return False

        # 3. DB Upsert 수행
        return favorite_repository.upsert_favorite(
            user_id=user_id,
            menu_id=item.menu_id,
            title=item.title,
            path=clean_path,
            icon=item.icon
        )

    def remove_favorite(self, favorite_id: int, user_id: int) -> bool:
        return favorite_repository.delete_by_id(favorite_id, user_id)


# 컨트롤러에서 Depends(get_favorite_service) 형태로 의존성 주입할 때 사용
favorite_service = FavoriteService()


def get_favorite_service() -> FavoriteService:
    return favorite_service