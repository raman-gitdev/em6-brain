# EM6 Brain - project state

_Last updated: 9 Oct 2026_

## Goal
A company "brain": an AI that understands carrier tariff files (Excel/PDF), maps them into the
rate hub, helps auditors, and later supports managers. Secure, local-first, built in stages.

## Stages
| Stage | What | Done when |
|---|---|---|
| **0 Foundations** (now) | Model on PC, chat app, Git, logging, test set | Chat works end to end, baseline score on test set |
| 1 Tools, read-only | Read/profile Excel, masters lookup, read-only rate hub queries | Identifies most test files correctly |
| 2 Mapping + memory | Brain writes mapping specs, loads to STAGING only, human approves, RAG memory | Known carriers approved without edits |
| 3 Controlled DB work | Publish staging -> live with audit + rollback; Architect (Claude API) proposes schema changes | Weeks with no rollbacks |
| 4 Auditors | Invoice vs contract checks, explain discrepancies | |
| 5 Management | Brainstorm, reports, what-if; every number cited | |
| 6 Voice | Speech-to-text, text-to-speech | |
| 7 Camera/body | Research, parked | |

## Decisions so far
- Pilot runs on Raman's PC (i5-7500, 16 GB RAM, no GPU). The Oracle NEXT ASYNC server is too small
  (1 core, 6 GB) and is not for EM6 data. A separate server comes later.
- Brain: Ollama, `qwen2.5:7b` (supports tool calling). Models on E: (SSD). Keep-alive 30 min.
  Measured: ~4.4 tokens/s writing, ~18-20 tokens/s reading, ~20 s first load.
- Ollama listens on 127.0.0.1 only.
- Stack: Angular front end, Python FastAPI backend, each tool a separate container, Postgres for
  logs (pgvector for RAG later), Docker Compose so the same setup moves to a server.
- Brain decides, program stays fixed: the brain outputs specs; a generic loader does the work.

## Stage 0 checklist
- [x] Ollama + qwen2.5:7b on PC, SSD, localhost only
- [x] App skeleton: orchestrator, clock-tool, Postgres log, Angular chat (streaming)
- [x] Docker Desktop engine won't start on the PC -> running without Docker via `run-local.ps1`
- [x] Local PostgreSQL 18: role `brain` + database `brain` created
- [x] First run with `run-local.ps1`: real model answered; called `get_current_time` on its own (298 ms); ~5 tok/s, ~11-12 s per short answer
- Note: until the PC restarts, start Ollama with `$env:OLLAMA_MODELS="E:\ollama\models"; ollama serve` (the old tray app looks at C:)
- [ ] Later: fix Docker Desktop (or use Docker on the server)
- [x] Git repo: private `raman-gitdev/em6-brain`, first commit pushed
- [ ] Test set: 20-30 already-loaded carrier files with known correct answers (kept outside Git)
- [ ] Baseline score recorded

## Stage 1 (started)
- [x] File upload in chat (📎). Files saved to `data/uploads/<file_id>/` with `meta.json`; .xlsx .xlsm .xls .csv, max 50 MB
- [x] `excel-tool`: `excel_profile` (sheets, title rows, likely header, sample rows, column types, merged cells),
      `excel_read_range` (max 400 cells), `excel_search`. Tested on anonymised sample files.
- [ ] Try on real carrier files from the test set; note where the profile or the model goes wrong
- [ ] PDF reading (text PDFs first), masters lookup, read-only rate hub queries
