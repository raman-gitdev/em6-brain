"""Talks to the brain (Ollama). Nothing else in the app knows Ollama's API."""
import json
from collections.abc import AsyncIterator

import httpx

from . import config


class BrainUnavailable(Exception):
    pass


async def status(client: httpx.AsyncClient) -> dict:
    """Is the brain reachable, and is the configured model installed?"""
    try:
        r = await client.get(f"{config.BRAIN_URL}/api/tags", timeout=5)
        r.raise_for_status()
        names = [m.get("name") for m in r.json().get("models", [])]
        return {"ok": config.BRAIN_MODEL in names, "url": config.BRAIN_URL,
                "model": config.BRAIN_MODEL, "model_installed": config.BRAIN_MODEL in names}
    except Exception as e:  # noqa: BLE001 - health check reports, never raises
        return {"ok": False, "url": config.BRAIN_URL, "model": config.BRAIN_MODEL,
                "error": f"{type(e).__name__}: {e}"}


async def stream_chat(client: httpx.AsyncClient, messages: list[dict],
                      tools: list[dict] | None) -> AsyncIterator[tuple[str, object]]:
    """Yields ("token", str), ("tool_calls", list) and finally ("done", stats)."""
    body = {"model": config.BRAIN_MODEL, "messages": messages, "stream": True,
            "options": {"num_ctx": config.BRAIN_NUM_CTX}}
    if tools:
        body["tools"] = tools
    try:
        async with client.stream("POST", f"{config.BRAIN_URL}/api/chat", json=body,
                                 timeout=httpx.Timeout(config.BRAIN_TIMEOUT_S, connect=10)) as r:
            if r.status_code != 200:
                detail = (await r.aread()).decode("utf-8", "replace")[:500]
                raise BrainUnavailable(f"Brain returned HTTP {r.status_code}: {detail}")
            async for line in r.aiter_lines():
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if "error" in chunk:
                    raise BrainUnavailable(f"Brain error: {chunk['error']}")
                msg = chunk.get("message") or {}
                if msg.get("content"):
                    yield "token", msg["content"]
                if msg.get("tool_calls"):
                    yield "tool_calls", msg["tool_calls"]
                if chunk.get("done"):
                    yield "done", {k: chunk.get(k) for k in (
                        "total_duration", "load_duration", "prompt_eval_count",
                        "prompt_eval_duration", "eval_count", "eval_duration")}
    except httpx.ConnectError as e:
        raise BrainUnavailable(
            f"Can't reach the brain at {config.BRAIN_URL}. Is Ollama running?") from e
    except httpx.TimeoutException as e:
        raise BrainUnavailable(
            f"The brain didn't answer within {config.BRAIN_TIMEOUT_S:.0f}s.") from e
