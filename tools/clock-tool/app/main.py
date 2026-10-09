"""clock-tool: the first, deliberately simple tool.

It exists to prove the tool contract end to end (/health, /describe, /run).
Copy this folder to start any new tool.
"""
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="clock-tool")

TOOLS = [{
    "name": "get_current_time",
    "description": "Get the current date and time. Use when the user asks about today's "
                   "date, the time, or the day of the week.",
    "parameters": {
        "type": "object",
        "properties": {
            "timezone": {"type": "string",
                         "description": "IANA time zone, e.g. Asia/Kolkata. Default Asia/Kolkata."},
        },
    },
}]


class RunRequest(BaseModel):
    name: str
    arguments: dict = {}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/describe")
def describe():
    return {"service": "clock-tool", "tools": TOOLS}


@app.post("/run")
def run(req: RunRequest):
    if req.name != "get_current_time":
        return {"ok": False, "error": f"clock-tool has no tool named '{req.name}'."}
    tz_name = req.arguments.get("timezone") or "Asia/Kolkata"
    try:
        now = datetime.now(ZoneInfo(tz_name))
    except (ZoneInfoNotFoundError, ValueError):
        return {"ok": False, "error": f"Unknown time zone '{tz_name}'."}
    return {"ok": True, "result": {"timezone": tz_name, "iso": now.isoformat(timespec="seconds"),
                                   "date": now.strftime("%d %B %Y"), "day": now.strftime("%A"),
                                   "time": now.strftime("%H:%M")}}
