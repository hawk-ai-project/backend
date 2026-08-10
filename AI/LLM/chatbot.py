from __future__ import annotations

from threading import Lock
from typing import Any

from AI.LLM.chatbot_prompt import SYSTEM_PROMPT, build_chat_prompt
from AI.LLM.config import BASE_MODEL_PATH


_model: Any | None = None
_tokenizer: Any | None = None
_model_lock = Lock()


def _validate_model_path() -> None:
    if not BASE_MODEL_PATH.is_dir():
        raise FileNotFoundError(f"Qwen 베이스 모델 디렉터리를 찾을 수 없습니다: {BASE_MODEL_PATH}")
    model_file = BASE_MODEL_PATH / "model.safetensors"
    if not model_file.is_file():
        raise FileNotFoundError(f"Qwen 모델 파일을 찾을 수 없습니다: {model_file}")


def load_model() -> tuple[Any, Any]:
    """챗봇용 Qwen Base Model을 최초 요청에서만 로드하고 재사용한다."""
    global _model, _tokenizer
    if _model is not None and _tokenizer is not None:
        return _model, _tokenizer

    with _model_lock:
        if _model is not None and _tokenizer is not None:
            return _model, _tokenizer
        _validate_model_path()
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as error:
            raise RuntimeError("챗봇 모델 실행 의존성이 설치되지 않았습니다.") from error

        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH, trust_remote_code=True)
        if tokenizer.pad_token_id is None:
            tokenizer.pad_token = tokenizer.eos_token
        model = AutoModelForCausalLM.from_pretrained(
            BASE_MODEL_PATH,
            torch_dtype=torch.float32,
            device_map="cpu",
            trust_remote_code=True,
        )
        model.eval()
        _model = model
        _tokenizer = tokenizer
        return _model, _tokenizer


def generate_answer(context: str, message: str) -> str:
    model, tokenizer = load_model()
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_chat_prompt(context, message)},
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
            max_new_tokens=320,
            do_sample=False,
            repetition_penalty=1.05,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    answer = tokenizer.decode(output_ids[0, input_length:], skip_special_tokens=True).strip()
    if not answer:
        raise ValueError("챗봇이 빈 응답을 생성했습니다.")
    return answer
