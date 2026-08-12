"""Forbidden-word configuration, scanning, and administrator review."""

import math
import re
from repository import forbidden_word_repository as repo
from service.auth_service import AuthError


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.casefold())


def _find_match(body: str, word: str) -> str | None:
    """Detect exact/obfuscated matches and one-character typos for 4+ chars."""
    normalized_body = _normalize(body)
    normalized_word = _normalize(word)
    if not normalized_word:
        return None
    if normalized_word in normalized_body:
        return word
    if len(normalized_word) < 4:
        return None
    size = len(normalized_word)
    for index in range(len(normalized_body) - size + 1):
        candidate = normalized_body[index:index + size]
        if sum(left != right for left, right in zip(candidate, normalized_word)) <= 1:
            return candidate
    return None


def _excerpt(body: str, word: str) -> str:
    index = body.casefold().find(word.casefold())
    if index < 0:
        return body.replace("\n", " ")[:500]
    start = max(0, index - 100); end = min(len(body), index + len(word) + 100)
    return body[start:end].replace("\n", " ")[:500]


def scan_content(content_type: str, content_id: int, body: str) -> int:
    repo.clear_open_flags(content_type, content_id)
    found = 0
    for item in repo.active_words():
        matched = _find_match(body or "", item["word"])
        if matched:
            repo.upsert_flag(item["id"], content_type, content_id, matched, _excerpt(body or "", item["word"]))
            found += 1
    return found


def rescan_all() -> int:
    return sum(scan_content(item["contentType"], item["contentId"], item["body"] or "") for item in repo.source_contents())


def list_words(): return repo.list_words()


def create_word(word: str, admin_id: int):
    clean = word.strip()
    if len(clean) < 2: raise AuthError("금칙어는 2자 이상이어야 합니다.", 422)
    try: word_id = repo.create_word(clean, _normalize(clean), admin_id)
    except Exception as exc:
        if "duplicate" in str(exc).lower(): raise AuthError("이미 등록된 금칙어입니다.", 409) from None
        raise
    rescan_all()
    return next(item for item in repo.list_words() if item["id"] == word_id)


def toggle_word(word_id: int, active: bool):
    if not repo.set_active(word_id, active): raise AuthError("금칙어를 찾을 수 없습니다.", 404)
    rescan_all()
    return {"id": word_id, "isActive": active}


def delete_word(word_id: int):
    if not repo.delete_word(word_id): raise AuthError("금칙어를 찾을 수 없습니다.", 404)


def list_flags(page, page_size, status, content_type):
    items,total=repo.list_flags(page,page_size,status,content_type)
    return {"items":items,"page":page,"pageSize":page_size,"totalItems":total,"totalPages":math.ceil(total/page_size) if total else 0}


def resolve(flag_id: int, status: str, note: str, admin_id: int):
    if not repo.resolve_flag(flag_id,status,note.strip(),admin_id): raise AuthError("탐지 결과를 찾을 수 없습니다.",404)
    return {"id":flag_id,"status":status}
