from starlette.requests import Request
from starlette.responses import Response

from controller.auth_controller import _set_refresh_cookie


def _request(scheme: str, forwarded_proto: str | None = None) -> Request:
    headers = []
    if forwarded_proto:
        headers.append((b"x-forwarded-proto", forwarded_proto.encode()))
    return Request({
        "type": "http", "method": "POST", "scheme": scheme,
        "path": "/api/auth/login", "raw_path": b"/api/auth/login",
        "query_string": b"", "headers": headers,
        "server": ("testserver", 80), "client": ("127.0.0.1", 1234),
    })


def test_refresh_cookie_is_usable_over_direct_http():
    response = Response()
    _set_refresh_cookie(_request("http"), response, "token", 1800)
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" not in cookie


def test_refresh_cookie_stays_secure_behind_https_proxy():
    response = Response()
    _set_refresh_cookie(_request("http", "https"), response, "token", 1800)
    assert "secure" in response.headers["set-cookie"].lower()
