"""Persistent application setting access."""

from typing import Any

from common.db import execute_query, fetch_query


DEFAULTS = {
    "signup_enabled": "true",
    "board_write_enabled": "true",
    "inspection_notification_enabled": "false",
    "session_expire_minutes": "30",
}


def get_all() -> dict[str, str]:
    rows = fetch_query("SELECT setting_key, setting_value FROM system_settings")
    values = DEFAULTS.copy()
    if isinstance(rows, list):
        values.update({row["setting_key"]: row["setting_value"] for row in rows})
    return values


def get_value(key: str, default: str | None = None) -> str | None:
    row = fetch_query(
        "SELECT setting_value FROM system_settings WHERE setting_key = %s",
        (key,), one=True,
    )
    return row["setting_value"] if isinstance(row, dict) else default


def save_all(values: dict[str, Any], updated_by: int) -> None:
    for key, value in values.items():
        execute_query(
            """INSERT INTO system_settings (setting_key, setting_value, updated_by)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE setting_value = VALUES(setting_value),
              updated_by = VALUES(updated_by), updated_at = UTC_TIMESTAMP(6)""",
            (key, str(value).lower() if isinstance(value, bool) else str(value), updated_by),
        )
