from pathlib import Path


LLM_DIR = Path(__file__).resolve().parent

MODEL_DIR = LLM_DIR / "models"

BASE_MODEL_PATH = MODEL_DIR / "Qwen"

BOARD_ADAPTER_PATH = (
    MODEL_DIR
    / "hawk-ai-board-lora-v2-e2"
)