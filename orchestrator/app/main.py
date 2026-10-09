"""Orchestrator: the only service the front end talks to.

It keeps the conversation, asks the brain, runs the tools the brain asks for,
and logs every step to Postgres.
"""
import json
import pathlib
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import brain, config, db
from .tools import ToolRegistry

SYSTEM_PROMPT = (pathlib.Path(__file__).parent / "prompts" / "system.md").read_text(encoding="utf-8")
registry = ToolRegistry(config.TOOL_SERVICES)
http: httpx.AsyncClient


@asynccontextmanager
async def lifespan(_: FastAPI):
    global http
    http = httpx.AsyncClient()
    await db.init(config.DATABASE_URL)
    yield
    await http.aclose()
    await db.close()


app = FastAPI(title="EM6 Brain orchestrator", lifespan=lifespan)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20000)
    conversation_id: uuid.UUID | None = None


def _event(**kw) -> bytes:
    return (json.dumps(kw, ensure_ascii=False) + "\n").encode("utf-8")


@app.get("/api/health")
async def health():
    try:
        await db.ping()
        database = {"ok": True}
    except Exception as e:  # noqa: BLE001
        database = {"ok": False, "error": str(e)}
    await registry.refresh(http)
    return {"brain": await brain.status(http), "database": database,
            "tools": registry.service_status}


@app.get("/api/conversations")
async def conversations():
    return await db.list_conversations()


@app.get("/api/conversations/{conversation_id}/messages")
async def conversation_messages(conversation_id: uuid.UUID):
    if not await db.conversation_exists(conversation_id):
        raise HTTPException(404, "Conversation not found")
    return await db.conversation_messages(conversation_id)


@app.post("/api/chat")
async def chat(req: ChatRequest):
    """Streams newline-delimited JSON events:
    conversation, token, tool, tool_result, done, error."""
    if req.conversation_id and not await db.conversation_exists(req.conversation_id):
        raise HTTPException(404, "Conversation not found")
    conv_id = req.conversation_id or await db.new_conversation(req.message.strip())
    await db.log_message(conv_id, "user", req.message)
    return StreamingResponse(_run_chat(conv_id), media_type="application/x-ndjson")


async def _run_chat(conv_id: uuid.UUID):
    yield _event(type="conversation", id=str(conv_id))
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    *await db.history(conv_id, config.HISTORY_MESSAGES)]
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
