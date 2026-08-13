from main import app


def test_fastapi_import_and_existing_routes():
    paths = app.openapi()["paths"]
    assert "/api/chat" in paths
    assert "/api/boards" in paths
    assert "/api/boards/ai/generate" in paths
    assert {"get", "post"} <= set(paths["/api/boards"])
    assert "patch" in paths["/api/boards/{board_id}"]
    assert "delete" in paths["/api/boards/{board_id}"]
    assert "post" in paths["/api/auth/refresh"]
    assert "get" in paths["/api/admin/ai/detections"]
    assert "patch" in paths["/api/admin/ai/detections/{detection_id}"]
    assert "post" in paths["/api/admin/ai/missed-detections"]
    assert "get" in paths["/api/admin/ai/statistics"]
    assert {"get", "post"} <= set(paths["/api/hokeytoon/{episode_id}/comments"])
    assert {"patch", "delete"} <= set(paths["/api/hokeytoon/comments/{comment_id}"])
