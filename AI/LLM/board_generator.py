from __future__ import annotations

import json
import logging
import re
from threading import Lock
from typing import Any

from AI.LLM.config import BASE_MODEL_PATH, BOARD_ADAPTER_PATH
from AI.LLM.prompts import SYSTEM_PROMPT, build_board_prompt


_model: Any | None = None
_tokenizer: Any | None = None
_model_lock = Lock()
logger = logging.getLogger(__name__)


def _validate_model_paths() -> None:
    if not BASE_MODEL_PATH.is_dir():
        raise FileNotFoundError(
            f"Qwen 베이스 모델 디렉터리를 찾을 수 없습니다: {BASE_MODEL_PATH}"
        )
    if not BOARD_ADAPTER_PATH.is_dir():
        raise FileNotFoundError(
            f"LoRA Adapter 디렉터리를 찾을 수 없습니다: {BOARD_ADAPTER_PATH}"
        )
    adapter_file = BOARD_ADAPTER_PATH / "adapter_model.safetensors"
    if not adapter_file.is_file():
        raise FileNotFoundError(
            f"LoRA 가중치 파일을 찾을 수 없습니다: {adapter_file}"
        )


def load_model() -> tuple[Any, Any]:
    """Qwen Base Model과 LoRA Adapter를 최초 요청에서 한 번만 로드한다."""
    global _model, _tokenizer
    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    with _model_lock:
        if _model is not None and _tokenizer is not None:
            return _model, _tokenizer

        _validate_model_paths()
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as error:
            raise RuntimeError(
                "AI 모델 실행 의존성이 설치되지 않았습니다. requirements.txt를 설치해 주세요."
            ) from error

        tokenizer = AutoTokenizer.from_pretrained(
            BASE_MODEL_PATH,
            trust_remote_code=True,
        )
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token

        base_model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_PATH,
            torch_dtype=torch.float32,
            device_map="cpu",
            trust_remote_code=True,
        )
        model = PeftModel.from_pretrained(base_model, BOARD_ADAPTER_PATH)
        model.eval()
        _model = model
        _tokenizer = tokenizer
        return _model, _tokenizer


def _extract_json_object(text: str) -> dict[str, Any]:
    """설명이나 코드블록이 섞인 모델 출력에서 첫 번째 JSON 객체를 추출한다."""
    cleaned_text = text.strip().lstrip("\ufeff")
    candidates = re.findall(
        r"```(?:json)?\s*(.*?)\s*```",
        cleaned_text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    candidates.append(cleaned_text)
    decoder = json.JSONDecoder()

    for candidate in candidates:
        candidate = candidate.strip()
        for start in (match.start() for match in re.finditer(r"\{", candidate)):
            try:
                parsed, _ = decoder.raw_decode(candidate[start:])
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed

    raise ValueError("AI 생성 결과가 올바른 JSON 형식이 아닙니다.")


def _normalize_plain_text_response(text: str) -> dict[str, str] | None:
    """JSON을 따르지 않은 일반 텍스트 응답을 게시글 초안 형식으로 정규화한다."""
    cleaned = re.sub(r"```(?:markdown|text)?\s*|```", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\|[^>]+\|>", "", cleaned).strip()
    # JSON처럼 시작했지만 파싱에 실패한 응답은 깨진 이스케이프가 섞인 경우가 많다.
    # 일반 텍스트로 처리하지 않고 호출부의 안전 초안으로 대체한다.
    if cleaned.startswith("{") or '"title"' in cleaned[:200].lower():
        return None
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return None

    def field_value(labels: tuple[str, ...]) -> str | None:
        label_pattern = "|".join(re.escape(label) for label in labels)
        match = re.search(
            rf"(?:^|\n)\s*(?:{label_pattern})\s*[:：]\s*(.+)",
            cleaned,
            flags=re.IGNORECASE,
        )
        return match.group(1).strip() if match else None

    title = field_value(("title", "제목"))
    summary = field_value(("summary", "요약"))
    content = field_value(("content", "본문", "내용"))

    first_line = re.sub(r"^[#*\-\s]+", "", lines[0]).strip()
    title = title or first_line[:120]
    content = content or "\n\n".join(lines)
    summary = summary or re.sub(r"\s+", " ", content)[:180]
    if not title or not summary or not content:
        return None
    return {"title": title, "summary": summary, "content": content}


def _clean_generated_value(value: str) -> str:
    """모델의 한자 혼입과 반복 문단을 제거해 게시글에 안전하게 표시한다."""
    # 서비스 출력은 한글·영문·숫자·기본 Markdown 기호만 허용한다.
    # 제어문자, zero-width 문자, 한자/아랍어/대리문자/개인영역 문자는 모두 제거한다.
    # Malformed AI output can contain literal Unicode escapes (for example
    # ``\\u200b``) and even unpaired surrogate values. Decode complete escapes
    # first so the allow-list below can remove unsafe characters consistently.
    def decode_unicode_escape(match: re.Match[str]) -> str:
        code_point = int(match.group(1), 16)
        if 0xD800 <= code_point <= 0xDFFF:
            return ""
        return chr(code_point)

    value = re.sub(r"\\u([0-9a-fA-F]{4})", decode_unicode_escape, value)
    value = re.sub(r"\\u[0-9a-fA-F]{0,3}", "", value)
    value = re.sub(
        r"[^\t\n\r\x20-\x7e\u00b7\u2013\u2014\u2018\u2019\u201c\u201d\u1100-\u11ff\u3130-\u318f\uac00-\ud7a3]",
        "",
        value,
    )
    value = re.sub(r"[ \t]+", " ", value).strip()

    unique_lines: list[str] = []
    seen_lines: set[str] = set()
    for line in value.splitlines():
        line = line.strip()
        comparison_key = re.sub(r"\s+", " ", line)
        if line and comparison_key not in seen_lines:
            unique_lines.append(line)
            seen_lines.add(comparison_key)
    return "\n\n".join(unique_lines).strip()


def _looks_like_serialized_draft(value: str) -> bool:
    """Detect a JSON draft accidentally inserted into one text field."""
    return bool(
        re.match(r"^\s*(?:```json\s*)?\{", value, flags=re.IGNORECASE)
        and re.search(r'"(?:title|summary|content)"\s*:', value, flags=re.IGNORECASE)
    )


def _has_corrupt_escape_junk(value: str) -> bool:
    """Detect truncated escape runs such as ``\\\\\\\혀\\혐`` in model output."""
    if not isinstance(value, str):
        return True
    # Markdown almost never needs a run of backslashes. A single escaped
    # punctuation mark is permitted, but malformed model output contains many
    # backslashes or a backslash followed by an unsupported escape character.
    if value.count("\\") >= 2:
        return True
    return bool(re.search(r"\\\\[^nrt\\\\\"'`*#()\[\]{}+\-]", value))


def _safe_draft(
    location: str,
    waste_summary: str,
    priority: str | None,
    notes: str | None,
) -> dict[str, str]:
    """모델 응답이 사용할 수 없을 때 입력값만으로 만드는 안전한 한국어 초안."""
    title = f"{location} 점검 결과 안내"
    summary = waste_summary.strip() or "점검 결과를 확인해 주세요."
    content_parts = [f"## 점검 결과\n\n- 장소: {location}\n- 탐지 결과: {summary}"]
    if priority and priority.strip():
        content_parts.append(f"## 우선순위\n\n{priority.strip()}")
    if notes and notes.strip():
        content_parts.append(f"## 현장 메모\n\n{notes.strip()}")
    content_parts.append("## 후속 조치\n\n탐지 결과를 확인한 후 현장 상황에 맞는 수거 및 후속 조치를 진행해 주세요.")
    return {"title": title, "summary": summary, "content": "\n\n".join(content_parts)}


def sanitize_board_draft(
    draft: dict[str, Any],
    *,
    location: str = "점검 현장",
    waste_summary: str = "점검 결과를 확인해 주세요.",
) -> dict[str, str]:
    """Ensure an AI draft is safe before it is stored or displayed."""
    values = {key: draft.get(key, "") for key in ("title", "summary", "content")}

    def fallback() -> dict[str, str]:
        clean_location = _clean_generated_value(location) or "점검 현장"
        clean_summary = _clean_generated_value(waste_summary) or "점검 결과를 확인해 주세요."
        if _looks_like_serialized_draft(clean_location):
            clean_location = "점검 현장"
        if _looks_like_serialized_draft(clean_summary):
            clean_summary = "점검 결과를 확인해 주세요."
        return {
            "title": f"{clean_location} 점검 결과",
            "summary": clean_summary,
            "content": (
                "## 점검 결과\n\n"
                f"- 점검 장소: {clean_location}\n"
                f"- 탐지 결과: {clean_summary}\n\n"
                "## 후속 조치\n\n탐지 결과를 확인한 후 필요한 조치를 진행해 주세요."
            ),
        }

    if any(not isinstance(value, str) for value in values.values()):
        return fallback()

    if values["title"] == "Inspection site inspection result" or (
        "## Inspection result" in values["content"]
        and "Location: Inspection site" in values["content"]
    ):
        return fallback()

    if any(_has_corrupt_escape_junk(value) for value in values.values()):
        return fallback()

    serialized_values = [value for value in values.values() if _looks_like_serialized_draft(value)]
    if serialized_values:
        try:
            return parse_response(serialized_values[0])
        except ValueError:
            return fallback()

    cleaned = {key: _clean_generated_value(value) for key, value in values.items()}
    return cleaned if all(cleaned.values()) else fallback()


def parse_response(text: str) -> dict[str, str]:
    """모델 출력에서 JSON 객체를 파싱하고 필수 문자열 필드를 검증한다."""
    try:
        parsed = _extract_json_object(text)
    except ValueError as error:
        logger.warning("Board AI returned non-JSON output: %r", text[:1000])
        parsed = _normalize_plain_text_response(text)
        if parsed is None:
            raise error
    if not isinstance(parsed, dict):
        raise ValueError("AI 생성 결과는 JSON 객체여야 합니다.")

    required_keys = ("title", "summary", "content")
    missing_keys = [key for key in required_keys if key not in parsed]
    if missing_keys:
        raise ValueError(f"AI 생성 결과에 필수 항목이 누락되었습니다: {missing_keys}")

    return sanitize_board_draft(parsed)

    result: dict[str, str] = {}
    for key in required_keys:
        value = parsed[key]
        if not isinstance(value, str):
            raise ValueError(f"AI 생성 결과의 {key}이(가) 비어 있거나 문자열이 아닙니다.")
        cleaned_value = _clean_generated_value(value)
        if not cleaned_value:
            raise ValueError(f"AI 생성 결과의 {key}이(가) 비어 있거나 문자열이 아닙니다.")
        result[key] = cleaned_value
    return result


def generate_board_post(
    location: str,
    waste_summary: str,
    priority: str | None = None,
    category: str | None = None,
    notes: str | None = None,
) -> dict[str, str]:
    """DB 저장 없이 게시판 초안의 제목, 요약, Markdown 본문만 생성한다."""
    model, tokenizer = load_model()
    user_prompt = build_board_prompt(
        location=location,
        waste_summary=waste_summary,
        priority=priority,
        category=category,
        notes=notes,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    )
    inputs = {key: value.to(model.device) for key, value in inputs.items()}
    input_length = inputs["input_ids"].shape[-1]

    import torch

    with torch.inference_mode():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=768,
            do_sample=False,
            repetition_penalty=1.15,
            no_repeat_ngram_size=4,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    generated_text = tokenizer.decode(
        output_ids[0, input_length:],
        skip_special_tokens=True,
    ).strip()
    try:
        return parse_response(generated_text)
    except ValueError:
        logger.warning("Board AI output was unusable; returning a safe input-based draft.")
        return _safe_draft(location, waste_summary, priority, notes)
