import json
import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from time import perf_counter
from typing import Any

from fastapi import HTTPException

from AI.LLM import chatbot
from repository import chat_repository


logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "AI" / "LLM" / "data"
PROJECT_KEYWORDS = (
    "담당", "담당자", "팀원", "역할", "구현", "개발", "기술스택", "기술 스택",
    "프론트", "백엔드", "frontend", "backend", "yolo", "llm", "모델", "아키텍처",
    "프로젝트", "김도하", "이중호", "이일권", "이동근", "장은재",
)
DYNAMIC_HINTS = ("최근", "최신", "마지막", "점검 목록", "점검 내역", "점검 결과", "점검 이력", "발견", "탐지")
COMPLEX_HISTORY_HINTS = ("특징", "경향", "비교", "분석", "공통점", "요약해", "설명해")


def _load_json(name: str) -> Any:
    with (DATA_DIR / name).open(encoding="utf-8") as file:
        return json.load(file)


def _normalize(value: str) -> str:
    return re.sub(r"[^0-9a-z가-힣]", "", value.lower())


def classify_intent(message: str) -> str:
    """외부 테스트용 경량 분류기. 실제 처리에서는 동적 패턴을 가장 먼저 검사한다."""
    normalized = message.lower()
    if any(keyword in normalized for keyword in PROJECT_KEYWORDS):
        return "PROJECT_INFO"
    if any(keyword in normalized for keyword in DYNAMIC_HINTS):
        return "INSPECTION_HISTORY"
    return "FAQ"


def _extract_limit(message: str, default: int) -> int:
    match = re.search(r"(\d+)\s*건", message)
    return min(max(int(match.group(1)), 1), 10) if match else default


def _find_known_filter(message: str, values: list[str]) -> str | None:
    normalized = message.lower()
    return next((value for value in values if value.lower() in normalized), None)


def _match_query_pattern(message: str) -> dict | None:
    normalized = message.lower()
    if not any(hint in normalized for hint in DYNAMIC_HINTS):
        return None
    if any(word in normalized for word in ("모델", "구현", "담당", "학습", "yolo", "llm")) and not any(
        word in normalized for word in ("최근", "최신", "마지막")
    ):
        return None

    location = _find_known_filter(message, chat_repository.find_location_names())
    waste = _find_known_filter(message, chat_repository.find_waste_names())
    patterns = {item["action"]: item for item in _load_json("query_patterns.json")}
    explicit_count = re.search(r"\d+\s*건", message) is not None

    if location and any(word in normalized for word in ("점검", "발견")):
        selected = patterns["GET_INSPECTIONS_BY_LOCATION"]
    elif waste and any(word in normalized for word in ("발견", "탐지", "점검")):
        selected = patterns["GET_INSPECTIONS_BY_WASTE"]
    elif explicit_count or any(phrase in normalized for phrase in ("점검 목록", "점검 내역", "몇 건")):
        selected = patterns["GET_RECENT_INSPECTIONS"]
    elif any(phrase in normalized for phrase in patterns["GET_LATEST_INSPECTION"]["patterns"]) or (
        any(word in normalized for word in ("최근", "최신", "마지막"))
        and any(word in normalized for word in ("점검", "탐지", "발견", "폐기물"))
    ):
        selected = patterns["GET_LATEST_INSPECTION"]
    else:
        return None

    return {
        **selected,
        "limit": _extract_limit(message, selected["default_limit"]),
        "location": location,
        "waste": waste,
        "complex": any(hint in normalized for hint in COMPLEX_HISTORY_HINTS),
    }


def _faq_exact(message: str, faqs: list[dict]) -> dict | None:
    normalized = _normalize(message)
    return next((faq for faq in faqs if normalized == _normalize(faq["question"])), None)


def _faq_score(message: str, faq: dict) -> float:
    normalized = _normalize(message)
    similarity = SequenceMatcher(None, normalized, _normalize(faq["question"])).ratio()
    keyword_score = 0
    for keyword in faq["keywords"]:
        compact = _normalize(keyword)
        if compact and compact in normalized:
            keyword_score += 2 if len(compact) >= 4 else 1
    return max(similarity * 3, float(keyword_score))


def _faq_keyword_match(message: str, faqs: list[dict]) -> dict | None:
    ranked = sorted(((_faq_score(message, faq), faq) for faq in faqs), key=lambda item: item[0], reverse=True)
    if not ranked:
        return None
    score, faq = ranked[0]
    return faq if score >= 2 else None


def _is_project_question(message: str) -> bool:
    normalized = message.lower()
    return any(keyword in normalized for keyword in PROJECT_KEYWORDS)


def _find_members(data: dict, term: str) -> list[dict]:
    term = term.lower()
    return [
        member for member in data["members"]
        if term in " ".join([member["role"], *member["features"]]).lower()
    ]


def _format_members(members: list[dict], heading: str) -> str:
    lines = [heading]
    lines.extend(
        f"- {member['name']} ({member['role']}): {', '.join(member['features'])}"
        for member in members
    )
    return "\n".join(lines)


def _project_template(message: str, data: dict) -> str:
    normalized = message.lower()
    project = data["project"]
    members = data["members"]

    if any(word in normalized for word in ("팀원별", "모든 팀원", "전체 팀원", "팀원 역할", "업무 분담")):
        return _format_members(members, "Hawk-AI 팀원별 담당 역할입니다.")
    for member in members:
        if member["name"] in message:
            return _format_members([member], f"{member['name']}의 프로젝트 담당 정보입니다.")

    asks_person = any(word in normalized for word in ("누가", "담당자", "담당했", "담당이"))
    for term, label in (("yolo", "YOLO"), ("llm", "LLM"), ("현장점검", "현장점검"), ("점검이력", "점검이력"), ("통계", "통계분석"), ("관리자", "관리자")):
        if term in normalized and asks_person:
            matched = _find_members(data, term)
            return _format_members(matched, f"{label} 관련 담당 정보입니다.") if matched else f"{label} 담당 정보는 프로젝트 자료에서 확인되지 않습니다."

    if "프론트" in normalized or "frontend" in normalized:
        return "프론트엔드는 Next.js와 React를 기반으로 HOME, 현장점검, 점검이력, 게시판, 통계분석, 로그인과 관리자 화면을 구성하고 백엔드 API와 연동합니다."
    if "백엔드" in normalized or "backend" in normalized or "아키텍처" in normalized or "구조" in normalized:
        return "프론트엔드는 Next.js와 React로 화면과 API 호출을 구성하고, 백엔드는 FastAPI의 controller·service·repository 계층을 통해 MySQL과 AI 기능을 연결합니다."
    if "기술" in normalized or "스택" in normalized:
        return f"Hawk-AI의 기술 스택은 {', '.join(project['techStack'])}입니다."
    if "모델" in normalized or "yolo" in normalized or "llm" in normalized or "ai" in normalized:
        return "Hawk-AI의 AI 구성은 다음과 같습니다.\n- " + "\n- ".join(project["ai"])
    if "기능" in normalized:
        return "Hawk-AI의 주요 기능은 다음과 같습니다.\n- " + "\n- ".join(project["features"])
    return f"{project['name']}는 {project['description']}입니다."


def _history_context(rows: list[dict]) -> str:
    return "조회된 실제 점검이력:\n\n" + "\n\n".join(_history_block(row) for row in rows)


def _history_block(row: dict) -> str:
    captured = row["capturedAt"].strftime("%Y-%m-%d %H:%M")
    lines = [f"점검 #{row['id']}", f"- 위치: {row['location']}", f"- 촬영 일시: {captured}"]
    fields = (
        ("제목", row.get("title")),
        ("상태", row.get("status")),
        ("우선순위", row.get("priority")),
        ("탐지 결과", row.get("wasteSummary")),
        ("현장 메모", row.get("notes")),
        ("AI 의견", row.get("aiOpinion")),
    )
    lines.extend(f"- {label}: {value}" for label, value in fields if value)
    return "\n".join(lines)


def _history_template(rows: list[dict]) -> str:
    heading = "가장 최근 점검 결과입니다." if len(rows) == 1 else f"최근 점검 결과 {len(rows)}건입니다."
    return heading + "\n\n" + "\n\n".join(_history_block(row) for row in rows)


def _generate(context: str, message: str) -> str:
    try:
        return chatbot.generate_answer(context, message)
    except FileNotFoundError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except (ImportError, RuntimeError, OSError) as error:
        raise HTTPException(status_code=503, detail=f"챗봇 모델을 사용할 수 없습니다: {error}") from error
    except ValueError as error:
        raise HTTPException(status_code=502, detail=f"챗봇 응답을 처리할 수 없습니다: {error}") from error


def _result(answer: str, intent: str, source_type: str, started: float, sources: list | None = None, records: int | None = None) -> dict:
    record_log = f" records={records}" if records is not None else ""
    logger.info("[CHAT] intent=%s source=%s%s elapsed=%.3fs", intent, source_type, record_log, perf_counter() - started)
    return {"answer": answer, "type": intent, "sourceType": source_type, "sources": sources or []}


def chat(message: str, user: dict | None) -> dict:
    started = perf_counter()

    query = _match_query_pattern(message)
    if query:
        if user is None:
            raise HTTPException(status_code=401, detail="점검이력 조회는 로그인이 필요합니다.")
        rows = chat_repository.find_inspection_history(
            limit=query["limit"],
            user_id=user["id"],
            is_admin=user.get("role") == "ADMIN",
            location=query["location"],
            waste=query["waste"],
        )
        if not rows:
            return _result("조건에 해당하는 점검 이력을 찾지 못했습니다.", "INSPECTION_HISTORY", "INSPECTION_DB", started, records=0)
        sources = [{"id": row["id"], "location": row["location"], "capturedAt": row["capturedAt"]} for row in rows]
        if query["complex"]:
            answer = _generate(_history_context(rows), message)
            return _result(answer, "INSPECTION_HISTORY", "QWEN", started, sources, len(rows))
        return _result(_history_template(rows), "INSPECTION_HISTORY", "INSPECTION_DB", started, sources, len(rows))

    if _is_project_question(message):
        answer = _project_template(message, _load_json("project_info.json"))
        return _result(answer, "PROJECT_INFO", "PROJECT_INFO", started)

    faqs = _load_json("faq.json")
    faq = _faq_exact(message, faqs)
    if faq:
        return _result(faq["answer"], "FAQ", "STATIC_FAQ", started)
    faq = _faq_keyword_match(message, faqs)
    if faq:
        return _result(faq["answer"], "FAQ", "STATIC_FAQ", started)

    ranked = sorted(faqs, key=lambda item: _faq_score(message, item), reverse=True)
    relevant = [item for item in ranked[:3] if _faq_score(message, item) > 0]
    context = "\n".join(f"- {item['question']}: {item['answer']}" for item in relevant)
    if not context:
        context = _load_json("project_info.json")["project"]["description"]
    return _result(_generate(context, message), "FAQ", "QWEN", started)
