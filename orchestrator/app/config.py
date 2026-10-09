"""All settings come from environment variables (see .env.example).

Moving the brain to another machine later = change BRAIN_URL only.
Adding a tool = add its URL to TOOL_SERVICES only.
"""
import os


def _list(name: str) -> list[str]:
    return [u.strip().rstrip("/") for u in os.getenv(name, "").split(",") if u.strip()]


BRAIN_URL = os.getenv("BRAIN_URL", "http://host.docker.internal:11434").rstrip("/")
BRAIN_MODEL = os.getenv("BRAIN_MODEL", "qwen2.5:7b")
BRAIN_NUM_CTX = int(os.getenv("BRAIN_NUM_CTX", "8192"))
BRAIN_TIMEOUT_S = float(os.getenv("BRAIN_TIMEOUT_S", "600"))

TOOL_SERVICES = _list("TOOL_SERVICES")
TOOL_TIMEOUT_S = float(os.getenv("TOOL_TIMEOUT_S", "30"))
TOOL_RESULT_MAX_CHARS = int(os.getenv("TOOL_RESULT_MAX_CHARS", "8000"))
MAX_TOOL_ROUNDS = int(os.getenv("MAX_TOOL_ROUNDS", "4"))

HISTORY_MESSAGES = int(os.getenv("HISTORY_MESSAGES", "20"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
