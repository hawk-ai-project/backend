from __future__ import annotations

import json
import re
from threading import Lock
from typing import Any

from AI.LLM.config import BASE_MODEL_PATH, BOARD_ADAPTER_PATH
from AI.LLM.prompts import SYSTEM_PROMPT, build_board_prompt


_model: Any | None = None
_tokenizer: Any | None = None
_model_lock = Lock()


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


def parse_response(text: str) -> dict[str, str]:
    """모델 출력에서 JSON 객체를 파싱하고 필수 문자열 필드를 검증한다."""
    cleaned_text = text.strip()
    code_block = re.fullmatch(
        r"```(?:json)?\s*(.*?)\s*```",
        cleaned_text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    if code_block:
        cleaned_text = code_block.group(1).strip()

    try:
        parsed = json.loads(cleaned_text)
    except json.JSONDecodeError as error:
        raise ValueError("AI 생성 결과가 올바른 JSON 형식이 아닙니다.") from error
    if not isinstance(parsed, dict):
        raise ValueError("AI 생성 결과는 JSON 객체여야 합니다.")

    required_keys = ("title", "summary", "content")
    missing_keys = [key for key in required_keys if key not in parsed]
    if missing_keys:
        raise ValueError(f"AI 생성 결과에 필수 항목이 누락되었습니다: {missing_keys}")

    result: dict[str, str] = {}
    for key in required_keys:
        value = parsed[key]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"AI 생성 결과의 {key}이(가) 비어 있거나 문자열이 아닙니다.")
        result[key] = value.strip()
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
            max_new_tokens=512,
            do_sample=False,
            repetition_penalty=1.05,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    generated_text = tokenizer.decode(
        output_ids[0, input_length:],
        skip_special_tokens=True,
    ).strip()
    return parse_response(generated_text)
