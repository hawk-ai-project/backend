# domain/board/board_service.py

import math

from fastapi import HTTPException

from domain.board import board_repository


def get_board_list(
    page: int,
    page_size: int,
    keyword: str | None = None,
):
    items, total = board_repository.find_all(
        page=page,
        page_size=page_size,
        keyword=keyword,
    )

    return {
        "items": items,
        "page": page,
        "pageSize": page_size,
        "totalItems": total,
        "totalPages": math.ceil(total / page_size) if total else 0,
    }


def get_board_detail(board_id: int):
    board = board_repository.find_by_id(board_id)

    if board is None:
        raise HTTPException(
            status_code=404,
            detail="게시글을 찾을 수 없습니다.",
        )

    return board