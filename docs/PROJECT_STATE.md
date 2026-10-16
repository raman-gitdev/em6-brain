# EM6 Brain - project state

_Last updated: 13 Oct 2026_

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
- [x] First real test: B1C06 (Japan domestic: consolidated district x weight, dangerous-goods table, district map, charter by km x truck)
  - Q1 "what is this file" mostly right, but the profile only showed the first table's first rows (missed weights to 100 kg, DG table, mapping, notes)
  - Q3 rate lookup: model INVENTED a table ("District A 1 kg = 100 JPY"). Root causes, both fixed:
    1. orchestrator didn't carry tool results to later turns -> brain answered blind (now replayed; latest profile always kept whole)
    2. profile too thin -> now covers every table block (header with column letters, all row labels, first/last rows), notes, repeated layouts compressed
  - Prompt now forbids example figures and asks for the source cell of every number; num_ctx 8192 -> 16384
- [x] `excel_lookup(row label, column header)`: one rate by labels, no row counting. Returns the cell
      and table title for every matching table (normal vs dangerous-goods etc). Row labels now carry rN.
      Tested on B1C06: Kanto/Up to 5 kg = E11 578, DG E32 1270; Charter 4 ton/Up to 50 km = I9 42800.
- [x] Status no longer flickers while answering: a service that doesn't answer keeps its last tool list;
      `is_loaded` returns None (unknown) instead of False on error; health is cached and reports the brain
      `busy` during a chat (shown as "(answering…)"); warm-up only when idle, all tools ok, prompt/tools changed.
- [x] Pattern catalogue (`knowledge/patterns/`): how-to-classify, air (zone / country-to-country /
      airport-to-airport / zone+postcode), ground (city lane / postcode LTL / region / district×weight /
      charter / parcel / step pricing). Codes only. Prompt tells the brain to classify a file, cite evidence
      cells, say which rate-hub approach fits and what's new with options (DB changes are proposals only).
- [ ] Re-run the B1C06 test after the fixes; then 2 more carriers
- [x] Knowledge library (RAG): `knowledge/` Markdown files + `knowledge-tool` (search + save-after-user-agrees),
      full-text index in `brain.knowledge_chunk`; core glossary added to every prompt. Starter docs: glossary,
      freight audit, rate structures, surcharges, modes, EM6 conventions, rate hub, carrier B1C06.
      Learned notes go to `knowledge/learned/` (not in Git) for the team to review.
- [ ] Team/auditors review the starter knowledge; add carrier notes as files are tested
- [x] Speed: a plain "Hello" in a new chat read 5,546 tokens (220 s at ~25 tok/s) + 21 s model load.
      Fixes: instructions + tool list cut from 8,357 to ~4,000 chars (compact core glossary; full one in
      industry/glossary.md; shorter tool descriptions; clock-tool no longer registered), and a background
      warm-up that pre-reads them on start and whenever the model was unloaded, so Ollama reuses that reading.
- [ ] Later: meaning-based search (embedding model in Ollama + pgvector) when the library grows
- [ ] PDF reading (text PDFs first), masters lookup, read-only rate hub queries
