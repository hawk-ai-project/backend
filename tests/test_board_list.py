from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from domain.board import Board
from service import board_service


client = TestClient(main.app)


def board_row(*, updated_at=None):
    return {
        "id": 1,
        "categoryId": 1,
        "category": "개발 기록",
        "title": "게시글",
        "summary": None,
        "content": "내용",
        "tags": ["테스트"],
        "author": {"id": 2, "name": "작성자", "profileImageUrl": None},
        "createdAt": datetime(2026, 8, 25, 12, 0),
        "updatedAt": updated_at,
        "viewCount": 0,
        "thumbnailUrl": None,
    }


def test_board_list_returns_200_when_updated_at_is_null():
    with patch.object(board_service.board_repository, "find_all", return_value=([board_row()], 1)):
        response = client.get("/api/boards?page=1&pageSize=10")

    assert response.status_code == 200
    assert response.json()["items"][0]["updatedAt"] is None


def test_board_list_returns_empty_page():
    with patch.object(board_service.board_repository, "find_all", return_value=([], 0)):
        response = client.get("/api/boards?page=1&pageSize=10")

    assert response.status_code == 200
    assert response.json() == {
        "items": [], "page": 1, "pageSize": 10, "totalItems": 0, "totalPages": 0,
    }


def test_board_list_returns_pagination_metadata():
    with patch.object(board_service.board_repository, "find_all", return_value=([board_row()], 21)) as find_all:
        response = client.get("/api/boards?page=2&pageSize=10")

    assert response.status_code == 200
    assert response.json() | {"items": []} == {
        "items": [], "page": 2, "pageSize": 10, "totalItems": 21, "totalPages": 3,
    }
    find_all.assert_called_once_with(2, 10, None, None)


def test_board_schema_accepts_nullable_database_updated_at():
    board = Board.model_validate(board_row(updated_at=None))

    assert board.updatedAt is None
