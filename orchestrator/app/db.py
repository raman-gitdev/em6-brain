"""Postgres access for conversations and the log trail."""
import json
import pathlib
import uuid

import asyncpg

_pool: asyncpg.Pool | None = None


async def init(url: str) -> None:
    global _pool
    _pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
    sql = (pathlib.Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
    async with _pool.acquire() as conn:
        await conn.execute(sql)


async def close() -> None:
    if _pool:
        await _pool.close()


async def ping() -> None:
    await _pool.fetchval("SELECT 1")


async def new_conversation(title: str) -> uuid.UUID:
    return await _pool.fetchval(
        "INSERT INTO brain.conversation (title) VALUES ($1) RETURNING conversation_id",
        title[:80] or "New chat",
    )


async def conversation_exists(conversation_id: uuid.UUID) -> bool:
    return bool(await _pool.fetchval(
        "SELECT 1 FROM brain.conversation WHERE conversation_id = $1", conversation_id))


async def log_message(conversation_id: uuid.UUID, role: str, content: str, *,
                      tool_name: str | None = None, tool_args: dict | None = None,
                      ok: bool | None = None, duration_ms: int | None = None,
                      model: str | None = None, stats: dict | None = None) -> None:
    await _pool.execute(
        """INSERT INTO brain.message
               (conversation_id, role, content, tool_name, tool_args, ok, duration_ms, model, stats)
           VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9::jsonb)""",
        conversation_id, role, content, tool_name,
        json.dumps(tool_args) if tool_args is not None else None,
        ok, duration_ms, model,
        json.dumps(stats) if stats is not None else None,
    )


async def history(conversation_id: uuid.UUID, limit: int) -> list[dict]:
    """Last `limit` user/assistant turns, oldest first, in Ollama message format."""
    rows = await _pool.fetch(
        """SELECT role, content FROM (
               SELECT message_id, role, content FROM brain.message
               WHERE conversation_id = $1 AND role IN ('user', 'assistant')
               ORDER BY message_id DESC LIMIT $2
           ) t ORDER BY message_id""",
        conversation_id, limit,
    )
    return [{"role": r["role"], "content": r["content"]} for r in rows]


async def list_conversations(limit: int = 50) -> list[dict]:
    rows = await _pool.fetch(
        """SELECT conversation_id, title, created_at FROM brain.conversation
           ORDER BY created_at DESC LIMIT $1""", limit)
    return [{"id": str(r["conversation_id"]), "title": r["title"],
             "created_at": r["created_at"].isoformat()} for r in rows]


async def conversation_messages(conversation_id: uuid.UUID) -> list[dict]:
    rows = await _pool.fetch(
        """SELECT role, content, tool_name, ok, duration_ms, created_at FROM brain.message
           WHERE conversation_id = $1 ORDER BY message_id""", conversation_id)
    return [{"role": r["role"], "content": r["content"], "tool_name": r["tool_name"],
             "ok": r["ok"], "duration_ms": r["duration_ms"],
             "created_at": r["created_at"].isoformat()} for r in rows]
