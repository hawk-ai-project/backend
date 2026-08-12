from fastapi import APIRouter, Depends, Response, status

from controller.auth_controller import current_auth
from domain.hokeytoon import HokeytoonComment, HokeytoonCommentCreate, HokeytoonCommentUpdate
from service import hokeytoon_comment_service


router = APIRouter(prefix="/api/hokeytoon", tags=["호키툰"])


@router.get("/{episode_id}/comments", response_model=list[HokeytoonComment])
def get_comments(episode_id: int):
    return hokeytoon_comment_service.list_comments(episode_id)


@router.post("/{episode_id}/comments", response_model=HokeytoonComment, status_code=status.HTTP_201_CREATED)
def create_comment(episode_id: int, payload: HokeytoonCommentCreate, auth=Depends(current_auth)):
    return hokeytoon_comment_service.create_comment(episode_id, payload, auth[0])


@router.patch("/comments/{comment_id}", response_model=HokeytoonComment)
def update_comment(comment_id: int, payload: HokeytoonCommentUpdate, auth=Depends(current_auth)):
    return hokeytoon_comment_service.update_comment(comment_id, payload, auth[0])


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, auth=Depends(current_auth)):
    hokeytoon_comment_service.delete_comment(comment_id, auth[0])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
