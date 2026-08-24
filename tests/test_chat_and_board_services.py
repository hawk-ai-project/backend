from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from fastapi import HTTPException

from client import ai_client
from domain.board import BoardAIGenerateRequest
from service import board_service, chat_service


def test_existing_response_contract_is_preserved():
    result = chat_service._result("answer", "FAQ", "QWEN", 0)
    assert {"answer", "type", "sourceType", "sources"} <= result.keys()
    assert result["answer"] == "answer"


def test_remote_intent_and_action_are_added_with_legacy_action():
    result = chat_service._result(
        "go",
        "FAQ",
        "QWEN",
        0,
        remote_intent="NAVIGATION",
        remote_action={"type": "NAVIGATE", "path": "/histories"},
    )
    assert result["intent"] == "NAVIGATION"
    assert result["action"]["path"] == "/histories"
    assert result["actions"] == [{"label": "점검이력 보기", "href": "/histories"}]


def test_exact_faq_does_not_call_ai_server():
    faq = chat_service._load_json("faq.json")[0]
    with patch.object(chat_service.ai_client, "generate_chat") as remote:
        with patch.object(chat_service, "_faq_exact", return_value=faq):
            result = chat_service.chat(faq["question"], None)
    remote.assert_not_called()
    assert result["sourceType"] == "STATIC_FAQ"


def test_project_info_does_not_call_ai_server():
    with patch.object(chat_service.ai_client, "generate_chat") as remote:
        with patch.object(chat_service, "_is_project_question", return_value=True):
            result = chat_service.chat("project question", None)
    remote.assert_not_called()
    assert result["sourceType"] == "PROJECT_INFO"


def history_query(complex_value=False):
    return {
        "limit": 1,
        "location": None,
        "waste": None,
        "complex": complex_value,
    }


def history_row():
    return {
        "id": 7,
        "location": "safe location",
        "capturedAt": datetime(2026, 8, 1, 12, 0),
        "title": "inspection",
        "status": "DONE",
        "priority": "NORMAL",
        "wasteSummary": "bottle 1",
        "notes": None,
        "aiOpinion": None,
    }


def test_simple_history_preserves_user_filter_and_skips_ai():
    repository = Mock(return_value=[history_row()])
    with patch.object(chat_service, "_match_query_pattern", return_value=history_query()):
        with patch.object(chat_service.chat_repository, "find_inspection_history", repository):
            with patch.object(chat_service.ai_client, "generate_chat") as remote:
                result = chat_service.chat("history", {"id": 11, "role": "USER"})
    repository.assert_called_once_with(
        limit=1, user_id=11, is_admin=False, location=None, waste=None
    )
    remote.assert_not_called()
    assert result["sourceType"] == "INSPECTION_DB"


def test_complex_history_sends_only_filtered_context_to_ai():
    with patch.object(chat_service, "_match_query_pattern", return_value=history_query(True)):
        with patch.object(
            chat_service.chat_repository, "find_inspection_history", return_value=[history_row()]
        ):
            with patch.object(
                chat_service.ai_client,
                "generate_chat",
                return_value={"answer": "analysis", "intent": "INSPECTION", "action": None},
            ) as remote:
                result = chat_service.chat("analyze", {"id": 11, "role": "USER"})
    context, message = remote.call_args.args
    assert "safe location" in context
    assert message == "analyze"
    assert result["intent"] == "INSPECTION"


def test_unauthenticated_history_access_stays_blocked():
    with patch.object(chat_service, "_match_query_pattern", return_value=history_query()):
        with pytest.raises(HTTPException) as caught:
            chat_service.chat("history", None)
    assert caught.value.status_code == 401


@pytest.mark.parametrize(
    "error, status",
    [
        (ai_client.AIConnectionError(), 503),
        (ai_client.AITimeoutError(), 504),
        (ai_client.AIResponseError(), 502),
    ],
)
def test_chat_ai_errors_map_to_required_http_status(error, status):
    with patch.object(chat_service.ai_client, "generate_chat", side_effect=error):
        with pytest.raises(HTTPException) as caught:
            chat_service._generate("context", "message")
    assert caught.value.status_code == status


def test_board_generation_does_not_persist_draft():
    payload = BoardAIGenerateRequest(location="beach", wasteSummary="bottle 1")
    draft = {"title": "title", "summary": "summary", "content": "content"}
    with patch.object(board_service.ai_client, "generate_board", return_value=draft):
        with patch.object(board_service.board_repository, "create") as create:
            result = board_service.generate_board_draft(payload)
    create.assert_not_called()
    assert result == draft


def test_board_timeout_maps_to_504_without_affecting_crud():
    payload = BoardAIGenerateRequest(location="beach", wasteSummary="bottle 1")
    with patch.object(
        board_service.ai_client, "generate_board", side_effect=ai_client.AITimeoutError()
    ):
        with pytest.raises(HTTPException) as caught:
            board_service.generate_board_draft(payload)
    assert caught.value.status_code == 504

def test_model_recommendation_uses_database_context():
    context = "DB model catalog with class accuracy"
    generated = {"answer": "use model-a", "intent": "MODEL_RECOMMENDATION", "action": None}
    with patch.object(chat_service.model_catalog_repository, "model_recommendation_context", return_value=context) as repository:
        with patch.object(chat_service.ai_client, "generate_chat", return_value=generated) as remote:
            result = chat_service.chat("어떤 YOLO 모델을 쓰면 좋아?", None)
    repository.assert_called_once_with()
    assert remote.call_args.args[:2] == (context, "어떤 YOLO 모델을 쓰면 좋아?")
    assert result["sourceType"] == "AI_MODEL_DB"
    assert result["type"] == "MODEL_RECOMMENDATION"
