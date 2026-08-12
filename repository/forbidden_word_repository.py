"""Forbidden-word configuration and content detection persistence."""

from typing import Any
from common.db import execute_query, fetch_query


def list_words() -> list[dict[str, Any]]:
    rows = fetch_query("""SELECT w.id, w.word, w.is_active AS isActive, w.created_at AS createdAt,
        u.name AS createdByName, (SELECT COUNT(*) FROM content_moderation_flags f WHERE f.forbidden_word_id=w.id AND f.status='OPEN') AS openCount
        FROM forbidden_words w LEFT JOIN users u ON u.id=w.created_by ORDER BY w.is_active DESC, w.word""")
    return rows if isinstance(rows, list) else []


def active_words() -> list[dict[str, Any]]:
    rows = fetch_query("SELECT id, word FROM forbidden_words WHERE is_active=TRUE ORDER BY id")
    return rows if isinstance(rows, list) else []


def create_word(word: str, normalized: str, admin_id: int) -> int:
    return execute_query("INSERT INTO forbidden_words (word, normalized_word, created_by) VALUES (%s,%s,%s)", (word, normalized, admin_id))


def set_active(word_id: int, active: bool) -> bool:
    return execute_query("UPDATE forbidden_words SET is_active=%s WHERE id=%s", (active, word_id)) > 0


def delete_word(word_id: int) -> bool:
    return execute_query("DELETE FROM forbidden_words WHERE id=%s", (word_id,)) > 0


def source_contents() -> list[dict[str, Any]]:
    rows = fetch_query("""SELECT 'BOARD' contentType,id contentId,CONCAT_WS(' ',title,summary,content) body FROM boards WHERE deleted_at IS NULL
        UNION ALL SELECT 'COMMENT',id,content FROM board_comments WHERE deleted_at IS NULL""")
    return rows if isinstance(rows, list) else []


def upsert_flag(word_id: int, content_type: str, content_id: int, matched: str, excerpt: str) -> None:
    execute_query("""INSERT INTO content_moderation_flags (forbidden_word_id,content_type,content_id,matched_text,excerpt)
        VALUES (%s,%s,%s,%s,%s) ON DUPLICATE KEY UPDATE matched_text=VALUES(matched_text),excerpt=VALUES(excerpt),
        status=IF(status='DISMISSED','DISMISSED','OPEN'),detected_at=UTC_TIMESTAMP(6)""", (word_id,content_type,content_id,matched,excerpt))


def clear_open_flags(content_type: str, content_id: int) -> None:
    execute_query("DELETE FROM content_moderation_flags WHERE content_type=%s AND content_id=%s AND status='OPEN'", (content_type,content_id))


def list_flags(page: int, page_size: int, status: str | None, content_type: str | None) -> tuple[list[dict[str, Any]], int]:
    where="WHERE 1=1"; params=[]
    if status: where+=" AND f.status=%s"; params.append(status)
    if content_type: where+=" AND f.content_type=%s"; params.append(content_type)
    count=fetch_query(f"SELECT COUNT(*) total FROM content_moderation_flags f {where}",tuple(params),one=True)
    rows=fetch_query(f"""SELECT f.id,f.content_type contentType,f.content_id contentId,w.word,f.matched_text matchedText,
        f.excerpt,f.status,f.detected_at detectedAt,f.resolution_note resolutionNote,
        CASE WHEN f.content_type='BOARD' THEN b.title ELSE cb.title END contentTitle,
        CASE WHEN f.content_type='BOARD' THEN b.author_id ELSE c.author_id END authorId,
        CASE WHEN f.content_type='BOARD' THEN bu.name ELSE cu.name END authorName
        FROM content_moderation_flags f JOIN forbidden_words w ON w.id=f.forbidden_word_id
        LEFT JOIN boards b ON f.content_type='BOARD' AND b.id=f.content_id LEFT JOIN users bu ON bu.id=b.author_id
        LEFT JOIN board_comments c ON f.content_type='COMMENT' AND c.id=f.content_id LEFT JOIN boards cb ON cb.id=c.board_id LEFT JOIN users cu ON cu.id=c.author_id
        {where} ORDER BY f.detected_at DESC LIMIT %s OFFSET %s""",(*params,page_size,(page-1)*page_size))
    return (rows if isinstance(rows,list) else []), int(count['total']) if isinstance(count,dict) else 0


def resolve_flag(flag_id: int, status: str, note: str, admin_id: int) -> bool:
    return execute_query("""UPDATE content_moderation_flags SET status=%s,resolution_note=%s,resolved_by=%s,resolved_at=UTC_TIMESTAMP(6)
        WHERE id=%s""",(status,note,admin_id,flag_id)) > 0
