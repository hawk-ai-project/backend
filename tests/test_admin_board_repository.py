from unittest.mock import patch

from repository import admin_repository


def test_admin_board_list_falls_back_to_created_at_when_updated_at_is_null():
    captured = []

    def fetch(sql, args=(), *, one=False):
        captured.append(sql)
        return {"total": 0} if one else []

    with patch.object(admin_repository, "fetch_query", side_effect=fetch):
        admin_repository.find_boards(1, 20, None, None)

    list_query = captured[1]
    assert "COALESCE(b.updated_at, b.created_at) AS updatedAt" in list_query
