"""Orchestrator: the only service the front end talks to.

It keeps the conversation, asks the brain, runs the tools the brain asks for,
and logs every step to Postgres.
"""
import asyncio
import json
import logging
import os
import pathlib
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import brain, config, db, files
from .tools import ToolRegistry

def _system_prompt() -> str:
    """Rules + the core glossary (knowledge/core/*.md), read fresh for each chat so edits apply at once."""
    text = (pathlib.Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")
    core = pathlib.Path(config.KNOWLEDGE_DIR) / "core"
    if core.is_dir():
        for f in sorted(core.glob("*.md")):
            text += "\n\n" + f.read_text(encoding="utf-8").strip()
    return text

registry = ToolRegistry(config.TOOL_SERVICES)
http: httpx.AsyncClient
log = logging.getLogger("uvicorn.error")
_warm_task: asyncio.Task | None = None
_warmed_for: tuple = ()      # (system prompt, tool names) the brain last pre-read
_active_chats = 0            # answers being written right now
_last_health: dict | None = None


def _signature() -> tuple:
    return (_system_prompt(), tuple(t["function"]["name"] for t in registry.ollama_tools()))


async def _warm() -> None:
    """Pre-read the instructions. Waits (up to 60 s) for every tool service, because the brain
    only reuses its reading if the next chat sends exactly the same tool list."""
    global _warmed_for
    t0 = time.monotonic()
    try:
        for _ in range(30):
            await registry.refresh(http)
            if all(s.get("ok") for s in registry.service_status.values()):
                break
            await asyncio.sleep(2)
        log.info("Brain warm-up started (reading instructions once)...")
        sig = _signature()
        await brain.warm_up(http, sig[0], registry.ollama_tools())
        _warmed_for = sig
        log.info("Brain warm-up done in %.0f s - new chats will start fast.", time.monotonic() - t0)
    except Exception as e:  # noqa: BLE001 - warm-up is a nicety, never fatal
        log.warning("Brain warm-up skipped: %s", e)


def _start_warm() -> None:
    """Start a background warm-up unless one is already running."""
    global _warm_task
    if _warm_task is None or _warm_task.done():
        _warm_task = asyncio.create_task(_warm())


@asynccontextmanager
async def lifespan(_: FastAPI):
    global http
    http = httpx.AsyncClient()
    os.makedirs(config.FILES_DIR, exist_ok=True)
    await db.init(config.DATABASE_URL)
    _start_warm()
    yield
    await http.aclose()
    await db.close()


app = FastAPI(title="EM6 Brain orchestrator", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: uuid.UUID | None = None
    attachments: list[str] = Field(default_factory=list, max_length=10)  # file_ids from /api/files


def _event(**kw) -> bytes:
    return (json.dumps(kw, ensure_ascii=False) + "\n").encode("utf-8")


@app.get("/api/health")
async def health():
    """While an answer is being written the PC is fully busy, so checks would time out and show
    everything red. Then the last known status is returned, with the brain marked busy."""
    global _last_health
    if _active_chats and _last_health:
        out = json.loads(json.dumps(_last_health))
        out["brain"].update(ok=True, busy=True, warming=False)
        return out
    try:
        await db.ping()
        database = {"ok": True}
    except Exception as e:  # noqa: BLE001
        database = {"ok": False, "error": str(e)}
    await registry.refresh(http)
    status = await brain.status(http)
    warming = _warm_task is not None and not _warm_task.done()
    tools_ok = all(s.get("ok") for s in registry.service_status.values())
    if status.get("ok") and not warming and tools_ok and not _active_chats:
        loaded = await brain.is_loaded(http)
        if loaded is False or _signature() != _warmed_for:   # unloaded (idle) or prompt/tools changed
            _start_warm()
            warming = True
    status["warming"] = warming
    status["busy"] = bool(_active_chats)
    _last_health = {"brain": status, "database": database, "tools": registry.service_status}
    return _last_health


@app.get("/api/conversations")
async def conversations():
    return await db.list_conversations()


@app.get("/api/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: uuid.UUID):
    if not await db.conversation_exists(conversation_id):
        raise HTTPException(404, "Conversation not found")
    return await db.conversation_messages(conversation_id)


@app.post("/api/files")
async def upload_file(file: UploadFile = File(...)):
    """Saves an attached file and returns its file_id for the next chat message."""
    meta = await files.save(file)
    return {"file_id": meta["file_id"], "name": meta["original_name"], "size": meta["size"]}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Streams newline-delimited JSON events:
    conversation, token, tool, tool_result, done, error."""
    if req.conversation_id and not await db.conversation_exists(req.conversation_id):
        raise HTTPException(404, "Conversation not found")
    content = req.message
    for file_id in req.attachments:
        meta = files.get(file_id)
        if not meta:
            raise HTTPException(400, f"Unknown attachment {file_id}")
        content += f"\n\n[Attached file: {meta['original_name']} | file_id: {file_id}]"
    conv_id = req.conversation_id or await db.new_conversation(req.message.strip())
    await db.log_message(conv_id, "user", content)
    return StreamingResponse(_run_chat(conv_id), media_type="application/x-ndjson")


def _add_now(messages: list[dict]) -> None:
    """Tell the brain the current date/time. Added to the end of the newest user message only
    (not stored, not in the system prompt), so the brain's saved reading of earlier text stays valid."""
    now = datetime.now(ZoneInfo(config.TIMEZONE))
    for m in reversed(messages):
        if m["role"] == "user":
            m["content"] = f"{m['content']}\n\n[Now: {now:%A %d %B %Y, %H:%M} ({config.TIMEZONE})]"
            return


def _replay(rows: list[dict]) -> list[dict]:
    """Turns stored messages back into what the brain saw, tool calls included.
    Newest tool results are kept whole; older ones are shortened to save memory."""
    keep_full = config.HISTORY_FULL_TOOL_RESULTS
    tool_rows = [i for i, r in enumerate(rows) if r["role"] == "tool"]
    full = set(tool_rows[-keep_full:]) if keep_full else set()
    latest_profile = [i for i in tool_rows if "profile" in (rows[i]["tool_name"] or "")]
    if latest_profile:                    # the file overview is always kept whole
        full.add(latest_profile[-1])
    out = []
    for i, r in enumerate(rows):
        if r["role"] != "tool":
            out.append({"role": r["role"], "content": r["content"]})
            continue
        content = r["content"]
        if i not in full and len(content) > 600:
            content = content[:600] + "\n...[older tool result shortened; call the tool again if needed]"
        out.append({"role": "assistant", "content": "", "tool_calls": [
            {"function": {"name": r["tool_name"] or "", "arguments": r["tool_args"] or {}}}]})
        out.append({"role": "tool", "tool_name": r["tool_name"] or "", "content": content})
    # never start mid-turn: drop anything before the first user message
    while out and out[0]["role"] != "user":
        out.pop(0)
    return out


async def _run_chat(conv_id: uuid.UUID):
    """Counts running answers so health checks and warm-ups leave the brain alone meanwhile."""
    global _active_chats
    _active_chats += 1
    try:
        async for chunk in _run_chat_inner(conv_id):
            yield chunk
    finally:
        _active_chats -= 1


async def _run_chat_inner(conv_id: uuid.UUID):
    yield _event(type="conversation", id=str(conv_id))
    try:
        messages = [{"role": "system", "content": _system_prompt()},
                    *_replay(await db.history(conv_id, config.HISTORY_MESSAGES))]
        _add_now(messages)
        await registry.refresh(http)
        tools = registry.ollama_tools()

        for round_no in range(config.MAX_TOOL_ROUNDS + 1):
            # Last round: no tools offered, so the brain has to answer.
            offer = tools if round_no < config.MAX_TOOL_ROUNDS else None
            content, calls, stats = "", [], None
            t0 = time.monotonic()
            async for kind, value in brain.stream_chat(http, messages, offer):
                if kind == "token":
                    content += value
                    yield _event(type="token", text=value)
                elif kind == "tool_calls":
                    calls.extend(value)
                elif kind == "done":
                    stats = value
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            if not calls:
                await db.log_message(conv_id, "assistant", content, model=config.BRAIN_MODEL,
                                     duration_ms=elapsed_ms, stats=stats)
                yield _event(type="done", stats=stats)
                return

            messages.append({"role": "assistant", "content": content, "tool_calls": calls})
            for call in calls:
                fn = call.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments") or {}
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                yield _event(type="tool", name=name, arguments=args)
                ok, result, ms = await registry.run(http, name, args)
                await db.log_message(conv_id, "tool", result, tool_name=name, tool_args=args,
                                     ok=ok, duration_ms=ms)
                yield _event(type="tool_result", name=name, ok=ok, duration_ms=ms)
                messages.append({"role": "tool", "tool_name": name, "content": result})

    except brain.BrainUnavailable as e:
        await db.log_message(conv_id, "error", str(e))
        yield _event(type="error", text=str(e))
    except Exception as e:  # noqa: BLE001 - the user must always get an answer
        text = f"Something went wrong: {type(e).__name__}: {e}"
        await db.log_message(conv_id, "error", text)
        yield _event(type="error", text=text)
