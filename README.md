# EM6 Brain

A chat app connected to a local AI model (the "brain"), with tools the brain can call.
Stage 0: chat, tool calling, and a full log of every question, answer and tool call.

## How it fits together

```
Browser ──> frontend (Angular, nginx)  :8080
               └─ /api ──> orchestrator (FastAPI)  :8000
                              ├─> brain: Ollama on Windows  :11434  (BRAIN_URL)
                              ├─> clock-tool, excel-tool (one service per tool)
                              └─> postgres (conversations + logs)  :5433
```

Everything except Ollama runs in Docker. Every port is bound to `127.0.0.1`,
so nothing is reachable from other machines.

## First run

1. Ollama running, with the model pulled: `ollama list` shows `qwen2.5:7b`.
2. Docker Desktop running.
3. In this folder:
   ```powershell
   Copy-Item .env.example .env      # then open .env and set POSTGRES_PASSWORD
   docker compose up -d --build
   ```
4. Open http://localhost:8080 . The bottom-left dots should all be green.

Useful:
- `docker compose ps` - what's running
- `docker compose logs -f orchestrator` - follow the app server's log
- http://localhost:8000/docs - the API, to try calls by hand
- `docker compose down` - stop (data is kept in the `pgdata` volume)

## Running locally: `npm run dev` (easiest)

1. Ollama running (`ollama list` shows the models).
2. In the `Brain` folder, in any terminal (VS Code's is fine):
   ```powershell
   npm run dev
   ```
   It reads `.env`, installs/updates packages, then starts clock-tool, excel-tool, orchestrator and
   frontend in this one terminal, each line labelled. **Ctrl+C stops everything.**
3. Open http://localhost:4200

## Running from VS Code's Run and Debug panel

1. Ollama running (`ollama list` shows the models).
2. Open the `Brain` folder in VS Code. Extensions needed: **Python** and **Python Debugger**.
3. Run and Debug panel (Ctrl+Shift+D) -> pick **EM6 Brain (all)** -> F5.
   It installs/updates packages, then starts clock-tool, excel-tool, orchestrator and frontend,
   each in its own VS Code terminal. Stop with Shift+F5.
4. Open http://localhost:4200

## Running without Docker (current setup on Raman's PC)

Docker Desktop isn't running on this PC yet, so the pilot runs directly:

- Postgres: the local PostgreSQL 18, database `brain`, user `brain` (password = `POSTGRES_PASSWORD` in `.env`).
- Start everything: `powershell -ExecutionPolicy Bypass -File .\run-local.ps1`
- Open http://localhost:4200 . Close the four "Brain - ..." windows to stop.
- Attached files are saved in `data\uploads\` (one folder per file). That folder is not in Git.

Same code as the Docker setup; only the addresses differ (localhost instead of container names).

## Tools

| Tool service | Tools the brain can call | Notes |
|---|---|---|
| clock-tool | `get_current_time` | Template for new tools |
| excel-tool | `excel_profile`, `excel_read_range`, `excel_search` | .xlsx .xlsm .xls .csv; read-only; never follows links, never runs macros or recalculates formulas |

## Adding a tool

1. Copy `tools/clock-tool` to `tools/<new-tool>` and change `app/main.py`.
   Keep the contract: `GET /health`, `GET /describe`, `POST /run`.
2. Add a service block for it in `docker-compose.yml`.
3. Add `http://<new-tool>:8000` to `TOOL_SERVICES` (comma-separated).
4. `docker compose up -d --build`

A tool that crashes or is slow only fails its own call; the chat keeps working.

## Moving the brain to a server later

Change `BRAIN_URL` in `.env`. Nothing else changes.
