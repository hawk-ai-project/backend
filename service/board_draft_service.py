"""Validation kept in the web backend for remotely generated board drafts."""

from typing import Any


def sanitize_board_draft(
    draft: dict[str, Any],
    *,
    location: str = "점검 현장",
    waste_summary: str = "점검 결과를 확인해 주세요.",
) -> dict[str, str]:
    clean_location = location.strip() or "점검 현장"
    clean_summary = waste_summary.strip() or "점검 결과를 확인해 주세요."
    fallback = {
        "title": f"{clean_location} 점검 결과",
        "summary": clean_summary,
        "content": (
            "## 점검 결과\n\n"
            f"- 점검 장소: {clean_location}\n"
            f"- 탐지 결과: {clean_summary}\n\n"
            "## 후속 조치\n\n탐지 결과를 확인하고 필요한 조치를 진행해 주세요."
        ),
    }
    result: dict[str, str] = {}
    for key in ("title", "summary", "content"):
        value = draft.get(key)
        if not isinstance(value, str) or not value.strip():
            return fallback
        result[key] = value.strip()
    return result
