import json
import logging
from unittest.mock import patch

import httpx
import pytest
from pydantic import ValidationError

from client import ai_client
from domain.chat import ChatRequest
from service import chat_service


def test_chat_request_without_history_is_compatible():
    request = ChatRequest(message="안녕")
    assert request.history == []


def test_chat_history_validation_and_limits():
    valid = ChatRequest(
        message="그럼 다른 건?",
        history=[
            {"role": "user", "content": "점심 뭐 먹을까?"},
            {"role": "assistant", "content": "제육볶음은 어때요?"},
        ],
    )
    assert len(valid.history) == 2

    with pytest.raises(ValidationError):
        ChatRequest(
            message="질문",
            history=[{"role": "system", "content": "금지"}],
        )
    with pytest.raises(ValidationError):
        ChatRequest(
            message="질문",
            history=[{"role": "user", "content": "   "}],
        )
    with pytest.raises(ValidationError):
        ChatRequest(
            message="질문",
            history=[{"role": "user", "content": str(index)} for index in range(13)],
        )
    with pytest.raises(ValidationError):
        ChatRequest(
            message="현재 질문",
            history=[{"role": "user", "content": "현재 질문"}],
        )


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("안녕", "CASUAL_CHAT"),
        ("오늘 너무 힘들었어", "CASUAL_CHAT"),
        ("점심 뭐 먹을까?", "CASUAL_CHAT"),
        ("최근 점검 결과 알려줘", "INSPECTION_HISTORY"),
        ("김도하 담당 기능 알려줘", "PROJECT_INFO"),
        ("게시글 작성 방법 알려줘", "FAQ"),
        ("YOLO 모델 설명해줘", "PROJECT_INFO"),
    ],
)
def test_intent_regression(message, expected):
    assert chat_service.classify_intent(message) == expected


def test_board_feature_recommendation_is_not_casual():
    assert chat_service._is_casual_chat("게시판 기능 추천해줘") is False


def test_casual_chat_forwards_history_and_preserves_response_contract():
    history = [
        {"role": "user", "content": "점심은 매운 음식이 좋아"},
        {"role": "assistant", "content": "제육볶음은 어때요?"},
    ]
    with patch.object(
        chat_service.ai_client,
        "generate_chat",
        return_value={"answer": "순두부찌개는 어때요?", "intent": "CASUAL_CHAT", "action": None},
    ) as remote:
        result = chat_service.chat("그럼 다른 건?", None, history)

    remote.assert_called_once_with("", "그럼 다른 건?", history=history)
    assert result["type"] == "CASUAL_CHAT"
    assert result["sourceType"] == "QWEN"
    assert result["intent"] == "CASUAL_CHAT"
    assert result["actions"] == []


def test_ai_client_includes_history_without_logging_content(caplog):
    captured = {}
    secret = "로그에 나오면 안 되는 사적인 대화"

    def handler(request):
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"answer": "응답", "intent": "CASUAL_CHAT", "action": None},
            request=request,
        )

    with caplog.at_level(logging.INFO, logger=ai_client.__name__):
        ai_client.generate_chat(
            "",
            "그럼 다른 건?",
            history=[{"role": "user", "content": secret}],
            transport=httpx.MockTransport(handler),
        )

    assert captured["history"] == [{"role": "user", "content": secret}]
    assert captured["message"] == "그럼 다른 건?"
    assert secret not in caplog.text
    assert "그럼 다른 건?" not in caplog.text


def test_navigation_precedes_faq_matching():
    result = chat_service.chat("게시판으로 이동해줘", None)
    assert result["intent"] == "NAVIGATION"
    assert result["actions"] == [{"label": "게시판 보기", "href": "/boards"}]
