from main import app


def test_fastapi_import_and_existing_routes():
    paths = app.openapi()["paths"]
    assert "/api/chat" in paths
    assert "/api/boards" in paths
    assert "/api/boards/ai/generate" in paths
    assert {"get", "post"} <= set(paths["/api/boards"])
    assert "patch" in paths["/api/boards/{board_id}"]
    assert "delete" in paths["/api/boards/{board_id}"]
