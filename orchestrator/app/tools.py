"""Tool registry. Every tool is a separate service with the same contract:

    GET  /health    -> {"ok": true}
    GET  /describe  -> {"service": "clock-tool",
                        "tools": [{"name", "description", "parameters"(JSON schema)}]}
    POST /run       {"name": "...", "arguments": {...}}
                    -> {"ok": true, "result": <any JSON>} or {"ok": false, "error": "..."}

A tool that is down or slow only fails its own call; the chat carries on.
"""
import json
import time

import httpx

from . import config


class ToolRegistry:
    def __init__(self, services: list[str]):
        self.services = services
        self._where: dict[str, str] = {}      # tool name -> service URL
        self._defs: list[dict] = []           # Ollama tool definitions
        self.service_status: dict[str, dict] = {}
        self._last: dict[str, dict] = {}      # service URL -> last good /describe answer

    async def refresh(self, client: httpx.AsyncClient) -> None:
        """Ask every service what it offers. A service that doesn't answer (down, or just slow
        because the PC is busy answering) keeps the tools it offered last time, so the tool list
        - and the brain's saved reading of it - doesn't flicker."""
        where, defs = {}, []
        for url in self.services:
            try:
                r = await client.get(f"{url}/describe", timeout=10)
                r.raise_for_status()
                info = r.json()
                self._last[url] = info
                self.service_status[url] = {"ok": True, "service": info.get("service"),
                                            "tools": [t["name"] for t in info.get("tools", [])]}
            except Exception as e:  # noqa: BLE001
                info = self._last.get(url, {})
                self.service_status[url] = {"ok": False, "error": f"{type(e).__name__}: {e}",
                                            "tools": [t["name"] for t in info.get("tools", [])]}
            for t in info.get("tools", []):
                if t["name"] in where:   # first service wins; never silently swap
                    continue
                where[t["name"]] = url
                defs.append({"type": "function", "function": {
                    "name": t["name"], "description": t.get("description", ""),
                    "parameters": t.get("parameters", {"type": "object", "properties": {}})}})
        self._where, self._defs = where, defs

    def ollama_tools(self) -> list[dict]:
        return self._defs

    async def run(self, client: httpx.AsyncClient, name: str,
                  arguments: dict) -> tuple[bool, str, int]:
        """Returns (ok, text for the brain, duration_ms)."""
        t0 = time.monotonic()
        url = self._where.get(name)
        if not url:
            return False, f"Unknown tool '{name}'.", 0
        try:
            r = await client.post(f"{url}/run", json={"name": name, "arguments": arguments},
                                  timeout=config.TOOL_TIMEOUT_S)
            r.raise_for_status()
            data = r.json()
            ok = bool(data.get("ok"))
            payload = data.get("result") if ok else data.get("error", "Tool failed.")
            text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        except httpx.TimeoutException:
            ok, text = False, f"Tool '{name}' timed out after {config.TOOL_TIMEOUT_S:.0f}s."
        except Exception as e:  # noqa: BLE001
            ok, text = False, f"Tool '{name}' failed: {type(e).__name__}: {e}"
        if len(text) > config.TOOL_RESULT_MAX_CHARS:
            text = text[:config.TOOL_RESULT_MAX_CHARS] + "\n...[truncated]"
        return ok, text, int((time.monotonic() - t0) * 1000)
