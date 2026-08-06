# domain/board/board_repository.py

BOARD_DATA = [
    {
        "id": 1,
        "category": "공지",
        "title": "Hawk-AI 게시판 테스트",
        "summary": "게시판 백엔드 연동 테스트용 게시글입니다.",
        "content": "# Hawk-AI 게시판\n\nFastAPI 연동 테스트입니다.",
        "tags": ["Hawk-AI", "테스트"],
        "author": {
            "id": 1,
            "name": "관리자",
        },
        "createdAt": "2026-08-06T14:00:00",
        "updatedAt": "2026-08-06T14:00:00",
        "viewCount": 0,
        "thumbnailUrl": None,
    }
]


def find_all(
    page: int,
    page_size: int,
    keyword: str | None = None,
):
    posts = BOARD_DATA

    if keyword:
        normalized_keyword = keyword.lower()

        posts = [
            post
            for post in posts
            if normalized_keyword in post["title"].lower()
            or normalized_keyword in post["content"].lower()
        ]

    total = len(posts)
    start = (page - 1) * page_size
    end = start + page_size

    return posts[start:end], total


def find_by_id(board_id: int):
    return next(
        (
            post
            for post in BOARD_DATA
            if post["id"] == board_id
        ),
        None,
    )