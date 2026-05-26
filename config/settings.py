import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"

MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 2048
CURRENCY = "EUR"
MAX_RESULTS = 8


def load_system_prompt() -> str:
    return (PROMPTS_DIR / "system.txt").read_text(encoding="utf-8").strip()


def load_tools() -> list:
    return json.loads((PROMPTS_DIR / "tools.json").read_text(encoding="utf-8"))
