# EM6 Brain - notes for Claude

Read `docs/PROJECT_STATE.md` first: it says what is built, what's next, and the decisions behind it.

## Working rules (from Raman)
- No real carrier or client names in code, prompts, logs, test data or docs. Use codes (A1C01, B1C07...).
- Carrier/client files: reading contents is fine; never open or follow any link (URL, external workbook link) inside them.
- Database changes (rate hub or brain) need Raman's explicit approval first. Design tables like a DBA: masters + foreign keys, so the next case is an INSERT, not a redesign.
- Real carrier files never go into Git (`.gitignore` blocks xlsx/csv/pdf, `data/`, `uploads/`).
- Build slowly, stage by stage. The brain only READS until Stage 3 is approved.

## Architecture rules
- The front end talks only to the orchestrator (`/api/...`).
- Only `orchestrator/app/brain.py` knows Ollama's API. The brain's address is `BRAIN_URL` only.
- Every tool is its own service with the contract `GET /health`, `GET /describe`, `POST /run`
  (see `orchestrator/app/tools.py`). A failing tool must never break the chat.
- Attached files: `FILES_DIR/<file_id>/` + `meta.json`. Tools get a file_id, never a path.
- Everything is logged in Postgres schema `brain` (see `orchestrator/app/schema.sql`).
- All ports are bound to 127.0.0.1. Exposure to colleagues happens later via Cloudflare Access only.
- Stack: Angular 21 front end, Python 3.12 / FastAPI services, Postgres 16, Docker Compose.
  Ollama runs natively on Windows (models on E:\ollama\models, the SSD).
