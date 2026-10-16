"""tariff-insert-tool  — reads a carrier rate file and produces draft SQL INSERTs.

Contract (same as every brain tool):
    GET  /health   -> {"ok": true}
    GET  /describe -> {"service": "tariff-insert-tool", "tools": [...]}
    POST /run      -> {"name": "tariff_generate_inserts", "arguments": {...}}
               ->  {"ok": true,  "result": {"sql": "...", "rows": N, "output_file": "..."}}
            or ->  {"ok": false, "error": "..."}

The tool reads the Excel file from FILES_DIR/<file_id>/<original_name>,
works out the mode (ground / air / ocean) from the sheet structure,
and returns:
  - sql      : the full INSERT script as a string (also written to a .sql file)
  - rows     : number of data rows found
  - output_file : file name (caller can tell the user to download it)

Rules baked in:
  - Every INSERT has status='DRAFT'
  - source_ref / source_sheet / source_row filled from the actual file
  - carrier_code and carrier_name are set to the code the caller supplies
  - Nothing is invented: if a cell is empty the column is NULL / omitted
  - No real carrier or client names enter the SQL
"""
import csv
import datetime as dt
import json
import os
import re
import textwrap
import uuid
from pathlib import Path
from typing import Any

import openpyxl
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

FILES_DIR = os.environ.get("FILES_DIR", "/data/uploads")

app = FastAPI(title="tariff-insert-tool")

# ---------------------------------------------------------------------------
# Contract endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"ok": True}


@app.get("/describe")
def describe():
    return {
        "service": "tariff-insert-tool",
        "tools": [
            {
                "name": "tariff_generate_inserts",
                "description": (
                    "Read a carrier rate Excel file and produce draft SQL INSERT statements "
                    "for the tariff rate hub (tariff.ground_tariff, tariff.air_tariff, or "
                    "tariff.ocean_tariff). Returns the SQL as text AND writes a .sql file "
                    "to the uploads folder for download. Every INSERT has status='DRAFT'. "
                    "Call this instead of trying to generate INSERTs manually."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_id": {
                            "type": "string",
                            "description": "The file_id of the uploaded carrier rate Excel file."
                        },
                        "carrier_code": {
                            "type": "string",
                            "description": "Anonymous carrier code, e.g. B1C06. Never the real company name."
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["ground", "air", "ocean", "auto"],
                            "description": "Tariff type. Use 'auto' to let the tool decide from the file structure."
                        },
                        "valid_from": {
                            "type": "string",
                            "description": "Rate validity start date YYYY-MM-DD. If omitted, today is used."
                        },
                        "currency_code": {
                            "type": "string",
                            "description": "ISO 3-letter currency, e.g. JPY, USD, EUR. If omitted, tool tries to detect it."
                        }
                    },
                    "required": ["file_id", "carrier_code"]
                }
            }
        ]
    }


class RunRequest(BaseModel):
    name: str
    arguments: dict[str, Any]


@app.post("/run")
def run(req: RunRequest):
    if req.name != "tariff_generate_inserts":
        return JSONResponse({"ok": False, "error": f"Unknown tool '{req.name}'."}, status_code=400)
    try:
        result = generate_inserts(**req.arguments)
        return {"ok": True, "result": result}
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": str(e)}, status_code=200)


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------

def _find_file(file_id: str) -> tuple[str, str]:
    """Return (path, original_name). Raises if not found."""
    folder = Path(FILES_DIR) / file_id
    meta_path = folder / "meta.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"No file found for file_id '{file_id}'.")
    meta = json.loads(meta_path.read_text())
    name = meta.get("stored_name") or meta.get("original_name", "file.xlsx")
    path = folder / name
    if not path.exists():
        raise FileNotFoundError(f"File '{name}' missing from uploads folder.")
    return str(path), name


def _load_sheets(path: str) -> list[dict]:
    """Load all sheets as list of {name, rows:[]} dicts."""
    ext = Path(path).suffix.lower()
    if ext in (".xlsx", ".xlsm"):
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True,
                                    keep_links=False, keep_vba=False)
        sheets = []
        for ws in wb.worksheets:
            rows = []
            for row in ws.iter_rows(values_only=True):
                trimmed = list(row)
                while trimmed and trimmed[-1] is None:
                    trimmed.pop()
                rows.append(trimmed)
            sheets.append({"name": ws.title, "rows": rows})
        wb.close()
        return sheets
    if ext == ".xls":
        import xlrd
        book = xlrd.open_workbook(path, on_demand=True)
        sheets = []
        for sh in book.sheets():
            rows = []
            for r in range(sh.nrows):
                vals = [sh.cell(r, c).value for c in range(sh.ncols)]
                while vals and vals[-1] in (None, ""):
                    vals.pop()
                rows.append(vals)
            sheets.append({"name": sh.name, "rows": rows})
        book.release_resources()
        return sheets
    raise ValueError(f"Unsupported file type '{ext}'.")


def _cell(v: Any) -> str | None:
    """Safe SQL scalar string."""
    if v is None:
        return None
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, dt.datetime):
        return v.date().isoformat()
    if isinstance(v, dt.date):
        return v.isoformat()
    s = " ".join(str(v).split()).strip()
    return s if s else None


def _sq(v: Any) -> str:
    """Wrap in single quotes, escape internal quotes. Returns NULL for None."""
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def _detect_mode(sheets: list[dict]) -> str:
    """Guess ground / air / ocean from sheet names and headers."""
    names = " ".join(s["name"].lower() for s in sheets)
    # Check first-row headers of all sheets
    headers = ""
    for s in sheets:
        for row in s["rows"][:3]:
            headers += " ".join(str(c).lower() for c in row if c is not None) + " "

    if any(kw in names for kw in ("air", "flight", "awb", "iata")):
        return "air"
    if any(kw in names for kw in ("ocean", "sea", "fcl", "lcl", "vessel")):
        return "ocean"
    if any(kw in headers for kw in ("airport", "iata", "awb", "flight")):
        return "air"
    if any(kw in headers for kw in ("port of loading", "pol", "pod", "vessel", "fcl", "lcl")):
        return "ocean"
    return "ground"   # default


def _detect_currency(sheets: list[dict]) -> str | None:
    """Try to find a currency code in the first few rows of any sheet."""
    currencies = {"JPY", "USD", "EUR", "GBP", "CNY", "SGD", "AUD", "INR", "HKD", "THB", "KRW"}
    for s in sheets:
        for row in s["rows"][:20]:
            for cell in row:
                v = str(cell).strip().upper() if cell is not None else ""
                if v in currencies:
                    return v
                # look for embedded currency like "JPY 578" or "578 JPY"
                m = re.search(r'\b(' + '|'.join(currencies) + r')\b', v)
                if m:
                    return m.group(1)
    return None


def _find_header_row(rows: list[list], keywords: list[str]) -> int | None:
    """Return the index of the first row that contains at least 2 of the keywords."""
    kw_lower = [k.lower() for k in keywords]
    for i, row in enumerate(rows):
        row_text = " ".join(str(c).lower() for c in row if c is not None)
        hits = sum(1 for k in kw_lower if k in row_text)
        if hits >= 2:
            return i
    return None


def _is_numeric(v: Any) -> bool:
    if isinstance(v, (int, float)):
        return True
    try:
        float(str(v).replace(",", ""))
        return True
    except (ValueError, TypeError):
        return False


def _to_numeric(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Ground tariff extractor
# ---------------------------------------------------------------------------

def _extract_ground(sheets: list[dict], carrier_code: str,
                    valid_from: str, currency_code: str,
                    source_ref: str) -> list[str]:
    """
    Heuristic ground tariff extractor.
    Looks for sheets with weight-band tables (rows with numbers as rate values).
    Returns a list of INSERT statements.
    """
    inserts = []
    weight_keywords = ["kg", "weight", "up to", "from", "rate", "charge", "price", "amount"]

    for sheet in sheets:
        rows = sheet["rows"]
        sheet_name = sheet["name"]
        if not rows:
            continue

        # Find a header row
        hdr_idx = _find_header_row(rows, weight_keywords)
        if hdr_idx is None:
            # Try row 0 as header if sheet has numeric data
            hdr_idx = 0

        header = [str(c).strip() if c is not None else "" for c in rows[hdr_idx]]

        # Try to identify columns by name
        def col(keywords_: list[str]) -> int | None:
            for k in keywords_:
                for i, h in enumerate(header):
                    if k.lower() in h.lower():
                        return i
            return None

        dest_col   = col(["dest", "destination", "city", "area", "region", "zone", "district", "area"])
        rate_col   = col(["rate", "charge", "price", "amount", "fee"])
        wt_to_col  = col(["up to", "to kg", "weight", "kg", "max"])
        wt_fr_col  = col(["from", "min", "over"])
        min_col    = col(["min", "minimum"])
        basis_col  = col(["basis", "per", "unit"])

        # Walk data rows
        for row_idx in range(hdr_idx + 1, len(rows)):
            row = rows[row_idx]
            if not row:
                continue

            # Skip purely header-like or empty rows
            non_empty = [c for c in row if c is not None and str(c).strip()]
            if len(non_empty) < 2:
                continue

            # Must have at least one numeric value to be a rate row
            numerics = [c for c in row if _is_numeric(c)]
            if not numerics:
                continue

            rate_val = _to_numeric(row[rate_col]) if rate_col is not None and rate_col < len(row) else None
            if rate_val is None:
                # Try to pick the first numeric that looks like a rate (>0)
                for c in row:
                    n = _to_numeric(c)
                    if n is not None and n > 0:
                        rate_val = n
                        break
            if rate_val is None:
                continue

            dest_city = _cell(row[dest_col]) if dest_col is not None and dest_col < len(row) else None
            wt_to     = _to_numeric(row[wt_to_col]) if wt_to_col is not None and wt_to_col < len(row) else None
            wt_fr     = _to_numeric(row[wt_fr_col]) if wt_fr_col is not None and wt_fr_col < len(row) else None
            min_chg   = _to_numeric(row[min_col]) if min_col is not None and min_col < len(row) else None

            # Guess charge basis
            basis = None
            if basis_col is not None and basis_col < len(row):
                basis = _cell(row[basis_col])
            if basis is None:
                if wt_to is not None:
                    basis = "PER_SHIPMENT"
                else:
                    basis = "PER_KG"

            cols = [
                "carrier_id", "carrier_code", "carrier_name", "currency_code",
                "record_type", "service_type",
                "dest_city",
                "break_type", "weight_from_kg", "weight_to_kg",
                "charge_basis", "rate_value",
            ]
            vals = [
                "(SELECT carrier_id FROM tariff.carrier WHERE carrier_code = " + _sq(carrier_code) + ")",
                _sq(carrier_code),
                _sq(carrier_code),
                _sq(currency_code),
                _sq("FREIGHT"),
                _sq("GROUPAGE"),
                _sq(dest_city),
                _sq("WEIGHT" if wt_to is not None else "NONE"),
                str(wt_fr) if wt_fr is not None else "NULL",
                str(wt_to) if wt_to is not None else "NULL",
                _sq(basis),
                str(rate_val),
            ]

            if min_chg is not None:
                cols.append("min_charge")
                vals.append(str(min_chg))

            cols += ["valid_from", "source_ref", "source_sheet", "source_row", "status"]
            vals += [_sq(valid_from), _sq(source_ref), _sq(sheet_name), str(row_idx + 1), _sq("DRAFT")]

            ins = (
                f"INSERT INTO tariff.ground_tariff\n"
                f"  ({', '.join(cols)})\nVALUES\n  ({', '.join(vals)});"
            )
            inserts.append(ins)

    return inserts


# ---------------------------------------------------------------------------
# Air tariff extractor
# ---------------------------------------------------------------------------

def _extract_air(sheets: list[dict], carrier_code: str,
                 valid_from: str, currency_code: str,
                 source_ref: str) -> list[str]:
    inserts = []
    air_keywords = ["kg", "weight", "rate", "origin", "dest", "airport", "zone", "iata"]

    for sheet in sheets:
        rows = sheet["rows"]
        sheet_name = sheet["name"]
        if not rows:
            continue

        hdr_idx = _find_header_row(rows, air_keywords) or 0
        header = [str(c).strip() if c is not None else "" for c in rows[hdr_idx]]

        def col(kws: list[str]) -> int | None:
            for k in kws:
                for i, h in enumerate(header):
                    if k.lower() in h.lower():
                        return i
            return None

        orig_col   = col(["origin", "from", "departure", "iata_o"])
        dest_col   = col(["dest", "to", "arrival", "iata_d"])
        zone_col   = col(["zone", "rate group", "group"])
        rate_col   = col(["rate", "charge", "price"])
        wt_to_col  = col(["up to", "to kg", "max weight", "weight to"])
        wt_fr_col  = col(["from", "min weight", "weight from", "over"])
        svc_col    = col(["service", "level", "product"])

        for row_idx in range(hdr_idx + 1, len(rows)):
            row = rows[row_idx]
            if not row:
                continue
            non_empty = [c for c in row if c is not None and str(c).strip()]
            if len(non_empty) < 2:
                continue
            numerics = [c for c in row if _is_numeric(c)]
            if not numerics:
                continue

            rate_val = _to_numeric(row[rate_col]) if rate_col is not None and rate_col < len(row) else None
            if rate_val is None:
                for c in row:
                    n = _to_numeric(c)
                    if n is not None and n > 0:
                        rate_val = n
                        break
            if rate_val is None:
                continue

            origin  = _cell(row[orig_col]) if orig_col is not None and orig_col < len(row) else None
            dest    = _cell(row[dest_col]) if dest_col is not None and dest_col < len(row) else None
            zone    = _cell(row[zone_col]) if zone_col is not None and zone_col < len(row) else None
            wt_to   = _to_numeric(row[wt_to_col]) if wt_to_col is not None and wt_to_col < len(row) else None
            wt_fr   = _to_numeric(row[wt_fr_col]) if wt_fr_col is not None and wt_fr_col < len(row) else None
            svc     = _cell(row[svc_col]) if svc_col is not None and svc_col < len(row) else None

            cols = [
                "carrier_id", "carrier_code", "carrier_name", "currency_code",
                "origin_airport", "dest_airport", "rate_group",
                "service_level",
                "weight_from_kg", "weight_to_kg",
                "rate_value",
            ]
            vals = [
                "(SELECT carrier_id FROM tariff.carrier WHERE carrier_code = " + _sq(carrier_code) + ")",
                _sq(carrier_code),
                _sq(carrier_code),
                _sq(currency_code),
                _sq(origin),
                _sq(dest),
                _sq(zone),
                _sq(svc or "SL1"),
                str(wt_fr) if wt_fr is not None else "NULL",
                str(wt_to) if wt_to is not None else "NULL",
                str(rate_val),
            ]

            cols += ["valid_from", "source_ref", "source_sheet", "source_row", "status"]
            vals += [_sq(valid_from), _sq(source_ref), _sq(sheet_name), str(row_idx + 1), _sq("DRAFT")]

            ins = (
                f"INSERT INTO tariff.air_tariff\n"
                f"  ({', '.join(cols)})\nVALUES\n  ({', '.join(vals)});"
            )
            inserts.append(ins)

    return inserts


# ---------------------------------------------------------------------------
# Ocean tariff extractor
# ---------------------------------------------------------------------------

def _extract_ocean(sheets: list[dict], carrier_code: str,
                   valid_from: str, currency_code: str,
                   source_ref: str) -> list[str]:
    inserts = []
    ocean_keywords = ["port", "origin", "destination", "rate", "equipment", "container", "lcl", "fcl"]

    for sheet in sheets:
        rows = sheet["rows"]
        sheet_name = sheet["name"]
        if not rows:
            continue

        hdr_idx = _find_header_row(rows, ocean_keywords) or 0
        header = [str(c).strip() if c is not None else "" for c in rows[hdr_idx]]

        def col(kws: list[str]) -> int | None:
            for k in kws:
                for i, h in enumerate(header):
                    if k.lower() in h.lower():
                        return i
            return None

        orig_col  = col(["origin port", "pol", "loading", "from port", "origin"])
        dest_col  = col(["dest port", "pod", "discharge", "to port", "destination"])
        equip_col = col(["equipment", "container", "type", "equip"])
        rate_col  = col(["rate", "freight", "charge", "price", "amount"])
        basis_col = col(["basis", "per", "unit"])

        for row_idx in range(hdr_idx + 1, len(rows)):
            row = rows[row_idx]
            if not row:
                continue
            non_empty = [c for c in row if c is not None and str(c).strip()]
            if len(non_empty) < 2:
                continue
            numerics = [c for c in row if _is_numeric(c)]
            if not numerics:
                continue

            rate_val = _to_numeric(row[rate_col]) if rate_col is not None and rate_col < len(row) else None
            if rate_val is None:
                for c in row:
                    n = _to_numeric(c)
                    if n is not None and n > 0:
                        rate_val = n
                        break
            if rate_val is None:
                continue

            origin  = _cell(row[orig_col]) if orig_col is not None and orig_col < len(row) else None
            dest    = _cell(row[dest_col]) if dest_col is not None and dest_col < len(row) else None
            equip   = _cell(row[equip_col]) if equip_col is not None and equip_col < len(row) else None
            basis   = _cell(row[basis_col]) if basis_col is not None and basis_col < len(row) else "PER_CONTAINER"

            cols = [
                "carrier_id", "carrier_code", "carrier_name", "currency_code",
                "origin_port", "dest_port", "equipment_type",
                "charge_basis", "rate_value",
            ]
            vals = [
                "(SELECT carrier_id FROM tariff.carrier WHERE carrier_code = " + _sq(carrier_code) + ")",
                _sq(carrier_code),
                _sq(carrier_code),
                _sq(currency_code),
                _sq(origin),
                _sq(dest),
                _sq(equip),
                _sq(basis),
                str(rate_val),
            ]

            cols += ["valid_from", "source_ref", "source_sheet", "source_row", "status"]
            vals += [_sq(valid_from), _sq(source_ref), _sq(sheet_name), str(row_idx + 1), _sq("DRAFT")]

            ins = (
                f"INSERT INTO tariff.ocean_tariff\n"
                f"  ({', '.join(cols)})\nVALUES\n  ({', '.join(vals)});"
            )
            inserts.append(ins)

    return inserts


# ---------------------------------------------------------------------------
# Main entry
# ---------------------------------------------------------------------------

def generate_inserts(file_id: str, carrier_code: str, mode: str = "auto",
                     valid_from: str | None = None,
                     currency_code: str | None = None) -> dict:
    # Validate carrier code — must look like an anonymous code, not a real name
    if len(carrier_code) > 20 or " " in carrier_code:
        raise ValueError(
            f"carrier_code '{carrier_code}' looks like a real company name. "
            "Use an anonymous code like B1C06."
        )

    path, original_name = _find_file(file_id)
    sheets = _load_sheets(path)

    if not sheets:
        raise ValueError("The file has no readable sheets.")

    if valid_from is None:
        valid_from = dt.date.today().isoformat()

    if currency_code is None:
        currency_code = _detect_currency(sheets) or "XXX"

    if mode == "auto":
        mode = _detect_mode(sheets)

    # Carrier INSERT (always first)
    carrier_insert = textwrap.dedent(f"""\
        -- Step 1: add carrier (skip if already exists)
        INSERT INTO tariff.carrier (carrier_code, carrier_name, status)
        VALUES ({_sq(carrier_code)}, {_sq(carrier_code)}, 'ACTIVE')
        ON CONFLICT (carrier_code) DO NOTHING;
    """)

    # Extract rate rows
    if mode == "ground":
        rate_inserts = _extract_ground(sheets, carrier_code, valid_from, currency_code, original_name)
    elif mode == "air":
        rate_inserts = _extract_air(sheets, carrier_code, valid_from, currency_code, original_name)
    elif mode == "ocean":
        rate_inserts = _extract_ocean(sheets, carrier_code, valid_from, currency_code, original_name)
    else:
        raise ValueError(f"Unknown mode '{mode}'. Use ground, air, ocean, or auto.")

    header_comment = textwrap.dedent(f"""\
        -- =================================================================
        -- DRAFT INSERT script generated by tariff-insert-tool
        -- Carrier : {carrier_code}
        -- Mode    : {mode}
        -- Source  : {original_name}
        -- Currency: {currency_code}
        -- Valid from: {valid_from}
        -- Rows    : {len(rate_inserts)}
        --
        -- *** DRAFT ONLY — a human must review and approve before running ***
        -- =================================================================
    """)

    footer = "\n-- *** END OF DRAFT — review all values before running ***\n"

    full_sql = header_comment + "\n" + carrier_insert + "\n"
    if rate_inserts:
        full_sql += f"-- Step 2: {mode} rate rows\n"
        full_sql += "\n".join(rate_inserts)
    else:
        full_sql += f"-- WARNING: no rate rows detected in {mode} mode.\n"
        full_sql += "-- Check that the file has numeric data in a tabular layout.\n"
    full_sql += footer

    # Write .sql file to uploads so the user can download it
    out_name = f"{carrier_code}_{mode}_draft_{dt.date.today().isoformat()}.sql"
    out_folder = Path(FILES_DIR) / f"sql_{uuid.uuid4().hex}"
    out_folder.mkdir(parents=True, exist_ok=True)
    out_path = out_folder / out_name
    out_path.write_text(full_sql, encoding="utf-8")

    return {
        "mode": mode,
        "carrier_code": carrier_code,
        "currency_detected": currency_code,
        "valid_from": valid_from,
        "rows": len(rate_inserts),
        "output_file": out_name,
        "sql": full_sql,
        "note": (
            f"DRAFT only — {len(rate_inserts)} rate rows found. "
            "A human must review every value before running these INSERTs. "
            f"File saved as: {out_name}"
        )
    }
