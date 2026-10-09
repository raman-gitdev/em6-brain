"""excel-tool: lets the brain look inside an uploaded spreadsheet.

Read-only. Works on files uploaded through the chat (FILES_DIR/<file_id>/).
Output is short plain text, sized for a small model's memory.
"""
import json
import os
import re

from fastapi import FastAPI
from openpyxl.utils import get_column_letter, range_boundaries
from pydantic import BaseModel

from .workbook import Sheet, fmt, load

FILES_DIR = os.getenv("FILES_DIR", "/data/uploads")
PROFILE_MAX_ROWS = 400        # rows read per sheet for the profile
MAX_SHEETS = 12
MAX_COLS = 20
SAMPLE_ROWS = 5
MAX_RANGE_CELLS = 400
MAX_SEARCH_HITS = 30

app = FastAPI(title="excel-tool")

FILE_ID = {"type": "string", "description": "The file_id given when the file was attached."}
TOOLS = [
    {
        "name": "excel_profile",
        "description": "Overview of an attached spreadsheet: every sheet's size, title rows, "
                       "likely header row, sample data rows and column types. "
                       "Call this first whenever the user attaches a spreadsheet.",
        "parameters": {"type": "object", "properties": {"file_id": FILE_ID},
                       "required": ["file_id"]},
    },
    {
        "name": "excel_read_range",
        "description": "Read exact cell values from one sheet, e.g. range A1:H20. "
                       "Use after excel_profile when you need more detail.",
        "parameters": {"type": "object", "properties": {
            "file_id": FILE_ID,
            "sheet": {"type": "string", "description": "Sheet name exactly as in the profile."},
            "range": {"type": "string", "description": "Cell range like A1:H20 (max 400 cells)."},
        }, "required": ["file_id", "sheet", "range"]},
    },
    {
        "name": "excel_search",
        "description": "Find cells containing a word or phrase in any sheet, e.g. 'valid', "
                       "'fuel', 'currency', 'minimum'. Case-insensitive.",
        "parameters": {"type": "object", "properties": {
            "file_id": FILE_ID,
            "text": {"type": "string", "description": "Word or phrase to look for."},
        }, "required": ["file_id", "text"]},
    },
]


class RunRequest(BaseModel):
    name: str
    arguments: dict = {}


class ToolError(Exception):
    pass


@app.get("/health")
def health():
    return {"ok": os.path.isdir(FILES_DIR)}


@app.get("/describe")
def describe():
    return {"service": "excel-tool", "tools": TOOLS}


@app.post("/run")
def run(req: RunRequest):
    a = req.arguments
    try:
        if req.name == "excel_profile":
            return {"ok": True, "result": profile(a.get("file_id", ""))}
        if req.name == "excel_read_range":
            return {"ok": True, "result": read_range(a.get("file_id", ""), a.get("sheet", ""),
                                                     a.get("range", ""))}
        if req.name == "excel_search":
            return {"ok": True, "result": search(a.get("file_id", ""), a.get("text", ""))}
        return {"ok": False, "error": f"excel-tool has no tool named '{req.name}'."}
    except ToolError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:  # noqa: BLE001 - a bad file must never crash the service
        return {"ok": False, "error": f"Could not read the file: {type(e).__name__}: {e}"}


# ---------------------------------------------------------------- file lookup

def _resolve(file_id: str) -> tuple[str, dict]:
    file_id = (file_id or "").strip()
    if not re.fullmatch(r"[0-9a-f]{32}", file_id):
        raise ToolError(f"'{file_id}' is not a valid file_id.")
    folder = os.path.join(FILES_DIR, file_id)
    try:
        with open(os.path.join(folder, "meta.json"), encoding="utf-8") as f:
            meta = json.load(f)
    except FileNotFoundError:
        raise ToolError(f"No attached file with file_id {file_id}.") from None
    return os.path.join(folder, meta["stored_name"]), meta


def _sheet(sheets: list[Sheet], name: str) -> Sheet:
    for s in sheets:
        if s.name == name:
            return s
    for s in sheets:
        if s.name.strip().lower() == name.strip().lower():
            return s
    raise ToolError(f"No sheet named '{name}'. Sheets: {', '.join(s.name for s in sheets)}")


# ---------------------------------------------------------------- profile

def _filled(row: list[object]) -> int:
    return sum(1 for v in row if v is not None and str(v).strip() != "")


def _guess_header(rows: list[list[object]]) -> int | None:
    """Index of the first 'wide' row in the top 30: titles above a table are narrow."""
    top = rows[:30]
    widest = max((_filled(r) for r in top), default=0)
    if widest < 2:
        return None
    for i, r in enumerate(top):
        if _filled(r) >= max(2, 0.6 * widest):
            return i
    return None


def _kind(v: object) -> str | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, bool):
        return "text"
    if isinstance(v, (int, float)):
        return "number"
    if hasattr(v, "year"):
        return "date"
    return "text"


def _column_kinds(rows: list[list[object]], n_cols: int) -> str:
    """'A text, B-R number' style summary of what each column holds."""
    kinds = []
    for c in range(n_cols):
        counts: dict[str, int] = {}
        for r in rows:
            k = _kind(r[c]) if c < len(r) else None
            if k:
                counts[k] = counts.get(k, 0) + 1
        if not counts:
            kinds.append("empty")
        else:
            top, n = max(counts.items(), key=lambda kv: kv[1])
            kinds.append(top if n >= 0.8 * sum(counts.values()) else "mixed")
    parts, start = [], 0
    for c in range(1, n_cols + 1):
        if c == n_cols or kinds[c] != kinds[start]:
            a, b = get_column_letter(start + 1), get_column_letter(c)
            parts.append(f"{a if a == b else a + '-' + b} {kinds[start]}")
            start = c
    return ", ".join(parts)


def _row_text(row: list[object], n: int = MAX_COLS, width: int = 30) -> str:
    cells = [fmt(v, width) for v in row[:n]]
    more = f" | …(+{len(row) - n} cols)" if len(row) > n else ""
    return " | ".join(cells) + more


def profile(file_id: str) -> str:
    path, meta = _resolve(file_id)
    sheets = load(path, PROFILE_MAX_ROWS)
    out = [f"File: {meta['original_name']} ({meta.get('size', 0) / 1024:.0f} KB), "
           f"{len(sheets)} sheet(s): {', '.join(repr(s.name) for s in sheets)}"]
    for s in sheets[:MAX_SHEETS]:
        out.append("")
        merged = ("merged cells unknown" if s.merged is None else
                  f"{len(s.merged)} merged range(s)" +
                  (f" e.g. {', '.join(s.merged[:4])}" if s.merged else ""))
        out.append(f"Sheet '{s.name}': {s.n_rows} rows x {s.n_cols} cols, {merged}")
        rows = s.rows
        if not any(_filled(r) for r in rows):
            out.append("  (empty)")
            continue
        h = _guess_header(rows)
        if h is None:
            out.append("  No clear table found. First rows:")
            for i, r in enumerate(rows[:8]):
                if _filled(r):
                    out.append(f"  r{i + 1}: {_row_text(r, width=100)}")
            continue
        above = [(i, r) for i, r in enumerate(rows[:h]) if _filled(r)]
        if above:
            out.append("  Above the table:")
            for i, r in above[:6]:
                out.append(f"  r{i + 1}: {_row_text(r, width=100)}")
        out.append(f"  Likely header (row {h + 1}): {_row_text(rows[h])}")
        data = [(i, r) for i, r in enumerate(rows[h + 1:], start=h + 1) if _filled(r)]
        out.append("  First data rows:")
        for i, r in data[:SAMPLE_ROWS]:
            out.append(f"  r{i + 1}: {_row_text(r)}")
        width = min(max((len(r) for _, r in data), default=0), s.n_cols or 0) or len(rows[h])
        out.append(f"  Column types: {_column_kinds([r for _, r in data], min(width, 52))}")
        if s.n_rows > PROFILE_MAX_ROWS:
            out.append(f"  (profile read the first {PROFILE_MAX_ROWS} of {s.n_rows} rows)")
    if len(sheets) > MAX_SHEETS:
        out.append(f"\n(+{len(sheets) - MAX_SHEETS} more sheets not profiled)")
    return "\n".join(out)


# ---------------------------------------------------------------- read / search

def read_range(file_id: str, sheet: str, cell_range: str) -> str:
    path, _ = _resolve(file_id)
    try:
        c1, r1, c2, r2 = range_boundaries(cell_range.strip().upper())
    except (ValueError, TypeError):
        raise ToolError(f"'{cell_range}' is not a valid range. Use something like A1:H20.") from None
    if None in (c1, r1, c2, r2):
        raise ToolError("Give a full range with both corners, like A1:H20.")
    cells = (c2 - c1 + 1) * (r2 - r1 + 1)
    if cells > MAX_RANGE_CELLS:
        raise ToolError(f"Range has {cells} cells; the limit is {MAX_RANGE_CELLS}. Ask for a smaller range.")
    s = _sheet(load(path, r2), sheet)
    lines = [f"Sheet '{s.name}' {cell_range.upper()}:",
             "     " + " | ".join(get_column_letter(c) for c in range(c1, c2 + 1))]
    for r in range(r1, r2 + 1):
        row = s.rows[r - 1] if r - 1 < len(s.rows) else []
        vals = [fmt(row[c - 1], 40) if c - 1 < len(row) else "" for c in range(c1, c2 + 1)]
        lines.append(f"r{r}: " + " | ".join(vals))
    return "\n".join(lines)


def search(file_id: str, text: str) -> str:
    path, _ = _resolve(file_id)
    needle = (text or "").strip().lower()
    if len(needle) < 2:
        raise ToolError("Search text must be at least 2 characters.")
    hits, total = [], 0
    for s in load(path, 5000):
        for ri, row in enumerate(s.rows):
            for ci, v in enumerate(row):
                if v is not None and needle in str(v).lower():
                    total += 1
                    if len(hits) < MAX_SEARCH_HITS:
                        hits.append(f"'{s.name}'!{get_column_letter(ci + 1)}{ri + 1}: {fmt(v, 80)}")
    if not hits:
        return f"No cells contain '{text}' (searched the first 5000 rows of each sheet)."
    more = f"\n(+{total - len(hits)} more matches)" if total > len(hits) else ""
    return f"{total} match(es) for '{text}':\n" + "\n".join(hits) + more
