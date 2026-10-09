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


def _database_url() -> str:
    """DATABASE_URL if given; otherwise built from parts, with the password URL-encoded
    so characters like @ or : can't break it."""
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    from urllib.parse import quote
    pw = quote(os.getenv("POSTGRES_PASSWORD", ""), safe="")
    return (f"postgresql://{os.getenv('DB_USER', 'brain')}:{pw}@{os.getenv('DB_HOST', 'localhost')}"
            f":{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'brain')}")


DATABASE_URL = _database_url()

# Uploaded files live here, one folder per file: <FILES_DIR>/<file_id>/{meta.json, file}
FILES_DIR = os.getenv("FILES_DIR", "/data/uploads")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "50"))
ALLOWED_UPLOAD_TYPES = (".xlsx", ".xlsm", ".xls", ".csv")
