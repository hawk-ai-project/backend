from datetime import timedelta

from service.auth_service import _access_token_lifetime


def test_access_token_lifetime_matches_admin_session_policy():
    assert _access_token_lifetime(30) == timedelta(minutes=30)
    assert _access_token_lifetime(60) == timedelta(minutes=60)
    assert _access_token_lifetime(480) == timedelta(minutes=480)
    assert _access_token_lifetime(1440) == timedelta(minutes=1440)
