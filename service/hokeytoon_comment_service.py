from fastapi import HTTPException

from domain.hokeytoon import HokeytoonCommentCreate, HokeytoonCommentUpdate
from repository import hokeytoon_comment_repository


def _ensure_episode(episode_id: int) -> None:
    if episode_id not in range(1, 11):
        raise HTTPException(status_code=404, detail="호키툰 회차를 찾을 수 없습니다.")


def list_comments(episode_id: int) -> list[dict]:
    _ensure_episode(episode_id)
    return hokeytoon_comment_repository.find_all(episode_id)


def create_comment(episode_id: int, payload: HokeytoonCommentCreate, user: dict) -> dict:
    _ensure_episode(episode_id)
    if payload.parentId is not None:
        parent = hokeytoon_comment_repository.find_parent(episode_id, payload.parentId)
        if parent is None:
            raise HTTPException(status_code=404, detail="답글을 작성할 댓글을 찾을 수 없습니다.")
        if parent["parentId"] is not None:
            raise HTTPException(status_code=422, detail="대댓글에는 답글을 작성할 수 없습니다.")
    comment_id = hokeytoon_comment_repository.create(episode_id, user["id"], payload.model_dump())
    return hokeytoon_comment_repository.find_by_id(comment_id)


def _owned(comment_id: int, user: dict) -> dict:
    comment = hokeytoon_comment_repository.find_by_id(comment_id)
    if comment is None:
        raise HTTPException(status_code=404, detail="댓글을 찾을 수 없습니다.")
    if int(comment["author"]["id"]) != int(user["id"]):
        raise HTTPException(status_code=403, detail="작성자만 댓글을 변경할 수 있습니다.")
    return comment


def update_comment(comment_id: int, payload: HokeytoonCommentUpdate, user: dict) -> dict:
    _owned(comment_id, user)
    hokeytoon_comment_repository.update(comment_id, payload.model_dump())
    return hokeytoon_comment_repository.find_by_id(comment_id)


def delete_comment(comment_id: int, user: dict) -> None:
    _owned(comment_id, user)
    hokeytoon_comment_repository.soft_delete(comment_id)
