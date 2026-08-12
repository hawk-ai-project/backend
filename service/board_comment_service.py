"""게시판 댓글과 한 단계 대댓글 비즈니스 규칙."""

from fastapi import HTTPException

from domain.board import BoardCommentCreate, BoardCommentUpdate
from repository import board_comment_repository
from service import forbidden_word_service


def list_comments(board_id: int) -> list[dict]:
    if not board_comment_repository.board_exists(board_id):
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    return board_comment_repository.find_all(board_id)


def create_comment(board_id: int, payload: BoardCommentCreate, user: dict) -> dict:
    if not board_comment_repository.board_exists(board_id):
        raise HTTPException(status_code=404, detail="게시글을 찾을 수 없습니다.")
    if payload.parentId is not None:
        parent = board_comment_repository.find_parent(board_id, payload.parentId)
        if parent is None:
            raise HTTPException(status_code=404, detail="답글을 작성할 댓글을 찾을 수 없습니다.")
        if parent["parentId"] is not None:
            raise HTTPException(status_code=422, detail="대댓글에는 답글을 작성할 수 없습니다.")
    comment_id = board_comment_repository.create(board_id, user["id"], payload.model_dump())
    comment = board_comment_repository.find_by_id(comment_id)
    if comment is None:
        raise HTTPException(status_code=500, detail="작성한 댓글을 불러오지 못했습니다.")
    forbidden_word_service.scan_content("COMMENT", comment_id, comment.get("content") or "")
    return comment


def _owned_comment(comment_id: int, user: dict) -> dict:
    comment = board_comment_repository.find_by_id(comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    if int(comment["author"]["id"]) != int(user["id"]):
        raise HTTPException(status_code=403, detail="작성자만 댓글을 변경할 수 있습니다.")
    return comment


def update_comment(comment_id: int, payload: BoardCommentUpdate, user: dict) -> dict:
    _owned_comment(comment_id, user)
    board_comment_repository.update(comment_id, payload.model_dump())
    comment = board_comment_repository.find_by_id(comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    forbidden_word_service.scan_content("COMMENT", comment_id, comment.get("content") or "")
    return comment


def delete_comment(comment_id: int, user: dict) -> None:
    _owned_comment(comment_id, user)
    if not board_comment_repository.soft_delete(comment_id):
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
