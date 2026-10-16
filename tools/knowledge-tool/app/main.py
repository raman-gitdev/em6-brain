"""knowledge-tool: the brain's searchable library (the RAG part).

Source of truth: Markdown files in KNOWLEDGE_DIR. On start (and after every save) they are split
by heading into brain.knowledge_chunk, which has a full-text index. The index is small and can
always be rebuilt from the files.

Tools for the brain:
  knowledge_search  - find the sections that match a question or term
  knowledge_save    - store something a user explained, ONLY after the user agreed
"""
import datetime as dt
import os
import re
from contextlib import asynccontextmanager
from urllib.parse import quote

import asyncpg
from fastapi import FastAPI
from pydantic import BaseModel

KNOWLEDGE_DIR = os.getenv("KNOWLEDGE_DIR", "/knowledge")
LEARNED = "learned"
MAX_RESULTS = 5
MAX_CHUNK_CHARS = 2500
MAX_RESULT_CHARS = 1500
MAX_NOTE_CHARS = 2000

# The index is rebuilt from the files on every start, so the table is simply recreated.
SCHEMA = """
CREATE SCHEMA IF NOT EXISTS brain;
DROP TABLE IF EXISTS brain.knowledge_chunk;
CREATE TABLE brain.knowledge_chunk (
    chunk_id   bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    path       text        NOT NULL,              -- file, relative to the knowledge folder
    heading    text        NOT NULL,              -- '# title > ## section'
    body       text        NOT NULL,
    kind       text        NOT NULL CHECK (kind IN ('core', 'reviewed', 'learned')),
    tsv        tsvector    GENERATED ALWAYS AS (                 -- heading words count more
                   setweight(to_tsvector('english', heading), 'A') ||
                   setweight(to_tsvector('english', body), 'B')) STORED,
    indexed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX knowledge_chunk_tsv_idx ON brain.knowledge_chunk USING gin (tsv);
"""

_pool: asyncpg.Pool | None = None


def _database_url() -> str:
    if os.getenv("DATABASE_URL"):
        return os.environ["DATABASE_URL"]
    pw = quote(os.getenv("POSTGRES_PASSWORD", ""), safe="")
    return (f"postgresql://{os.getenv('DB_USER', 'brain')}:{pw}@{os.getenv('DB_HOST', 'localhost')}"
            f":{os.getenv('DB_PORT', '5432')}/{os.getenv('DB_NAME', 'brain')}")


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _pool
    _pool = await asyncpg.create_pool(_database_url(), min_size=1, max_size=3)
    async with _pool.acquire() as c:
        await c.execute(SCHEMA)
    await reindex()
    yield
    await _pool.close()


app = FastAPI(title="knowledge-tool", lifespan=lifespan)

TOOLS = [
    {
        "name": "knowledge_search",
        "description": "Search EM6 knowledge: freight/audit terms, rate file layouts, surcharges, EM6 rules, "
                       "rate hub, tariff file patterns (zone, lane, country, airport, charter), carrier notes.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "words to look for"},
        }, "required": ["query"]},
    },
    {
        "name": "knowledge_save",
        "description": "Save a user's explanation for next time. Only after the user said yes.",
        "parameters": {"type": "object", "properties": {
            "topic": {"type": "string", "description": "short topic"},
            "note": {"type": "string", "description": "the explanation, in the user's words"},
            "user_confirmed": {"type": "boolean", "description": "true only if the user agreed"},
        }, "required": ["topic", "note", "user_confirmed"]},
    },
]


class RunRequest(BaseModel):
    name: str
    arguments: dict = {}


@app.get("/health")
async def health():
    try:
        n = await _pool.fetchval("SELECT count(*) FROM brain.knowledge_chunk")
        return {"ok": True, "chunks": n}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}


@app.get("/describe")
def describe():
    return {"service": "knowledge-tool", "tools": TOOLS}


@app.post("/reindex")
async def reindex_endpoint():
    return {"ok": True, "chunks": await reindex()}


@app.post("/run")
async def run(req: RunRequest):
    a = req.arguments
    try:
        if req.name == "knowledge_search":
            return {"ok": True, "result": await search(str(a.get("query", "")))}
        if req.name == "knowledge_save":
            return await save(str(a.get("topic", "")), str(a.get("note", "")), a.get("user_confirmed") is True)
        return {"ok": False, "error": f"knowledge-tool has no tool named '{req.name}'."}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ------------------------------------------------------------------ indexing

def _kind(rel: str) -> str:
    top = rel.split("/", 1)[0]
    return "core" if top == "core" else "learned" if top == LEARNED else "reviewed"


def _chunks(text: str) -> list[tuple[str, str]]:
    """Split a Markdown file into (heading, body) by '#'/'##' headings; long bodies by paragraph."""
    title, out, heading, lines = "", [], "", []

    def flush():
        body = "\n".join(lines).strip()
        if not body:
            return
        head = f"{title} > {heading}" if heading and title else (heading or title or "(untitled)")
        while len(body) > MAX_CHUNK_CHARS:
            cut = body.rfind("\n\n", 0, MAX_CHUNK_CHARS)
            cut = cut if cut > 200 else MAX_CHUNK_CHARS
            out.append((head, body[:cut].strip()))
            body = body[cut:].strip()
        out.append((head, body))

    for line in text.splitlines():
        if line.startswith("# "):
            flush()
            title, heading, lines = line[2:].strip(), "", []
        elif line.startswith("## "):
            flush()
            heading, lines = line[3:].strip(), []
        else:
            lines.append(line)
    flush()
    return out


async def reindex() -> int:
    rows = []
    for folder, _, files in os.walk(KNOWLEDGE_DIR):
        for f in sorted(files):
            if not f.endswith(".md") or f.lower() == "readme.md":
                continue
            path = os.path.join(folder, f)
            rel = os.path.relpath(path, KNOWLEDGE_DIR).replace(os.sep, "/")
            with open(path, encoding="utf-8") as fh:
                for heading, body in _chunks(fh.read()):
                    rows.append((rel, heading, body, _kind(rel)))
    async with _pool.acquire() as c, c.transaction():
        await c.execute("DELETE FROM brain.knowledge_chunk")
        await c.executemany(
            "INSERT INTO brain.knowledge_chunk (path, heading, body, kind) VALUES ($1, $2, $3, $4)", rows)
    return len(rows)


# ------------------------------------------------------------------ search / save

async def search(query: str) -> str:
    words = [w.lower() for w in re.findall(r"[A-Za-z0-9]+", query) if len(w) >= 2][:12]
    if not words:
        return "Give a few words to search for."
    tsq = " | ".join(words)        # any word may match; ranking puts the best sections first
    rows = await _pool.fetch(
        """SELECT path, heading, body, kind, ts_rank_cd(tsv, q) AS rank
           FROM brain.knowledge_chunk, to_tsquery('english', $1) q
           WHERE tsv @@ q ORDER BY rank DESC, length(body) LIMIT $2""",
        tsq, MAX_RESULTS)
    if not rows:
        return (f"Nothing in the knowledge library matches '{query}'. If the meaning is still unclear, "
                f"ask the user, then offer to save their explanation with knowledge_save.")
    parts = []
    for r in rows:
        label = " [learned from a user - not yet reviewed]" if r["kind"] == "learned" else ""
        body = r["body"] if len(r["body"]) <= MAX_RESULT_CHARS else r["body"][:MAX_RESULT_CHARS] + " …"
        parts.append(f"### {r['heading']}  ({r['path']}){label}\n{body}")
    return "\n\n".join(parts)


_PRICE = re.compile(
    r"(\d[\d,.]*\s*(JPY|USD|EUR|INR|CNY|GBP|SGD|AED|yen|rs\.?|rupees?)\b)"
    r"|((JPY|USD|EUR|INR|CNY|GBP|SGD|AED|rs\.?)\s*\d)"
    r"|([$\u20ac\u00a5\u20b9\u00a3]\s*\d)"
    r"|(\b(rate|price|cost|fare|tariff|charge)s?\b[^.\n]{0,40}\d)", re.IGNORECASE)


def _looks_like_price(text: str) -> bool:
    """Rates belong in the rate hub, never in the knowledge library (they change and must be traceable)."""
    return bool(_PRICE.search(text))


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "note"


async def save(topic: str, note: str, confirmed: bool) -> dict:
    if not confirmed:
        return {"ok": False, "error": "Not saved: ask the user first and call again with user_confirmed=true "
                                      "only after they agree."}
    topic, note = topic.strip()[:80], note.strip()
    if not topic or not note:
        return {"ok": False, "error": "Both topic and note are needed."}
    if _looks_like_price(topic + " " + note):
        return {"ok": False, "error": "Not saved: the knowledge library never stores rates or prices. "
                                      "Tell the user that rates live in the rate file / rate hub, not in memory."}
    if len(note) > MAX_NOTE_CHARS:
        return {"ok": False, "error": f"Note is too long ({len(note)} chars); keep it under {MAX_NOTE_CHARS}."}
    folder = os.path.join(KNOWLEDGE_DIR, LEARNED)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, _slug(topic) + ".md")
    new = not os.path.exists(path)
    today = dt.date.today().isoformat()
    with open(path, "a", encoding="utf-8") as f:
        if new:
            f.write(f"# Learned: {topic}\n")
        f.write(f"\n## {topic} (saved {today}, not yet reviewed)\n{note}\n")
    await reindex()
    return {"ok": True, "result": f"Saved to the knowledge library as learned/{os.path.basename(path)} "
                                  f"(marked 'not yet reviewed')."}
