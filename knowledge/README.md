# EM6 Brain knowledge library

Plain Markdown files. The brain searches them with the `knowledge_search` tool.

| Folder | What | Who writes it |
|---|---|---|
| `core/` | Short glossary the brain ALWAYS sees (keep it under ~2 pages) | Team, reviewed |
| `industry/` | Freight and audit concepts | Team, reviewed |
| `em6/` | How EM6 works: codes, rules, the rate hub | Team, reviewed |
| `carriers/` | One file per carrier code: layout and quirks of its files | Team, reviewed |
| `learned/` | Notes the brain saved after a user explained something (user said "yes, save it") | The brain - NOT reviewed, not in Git |

## Rules
- One topic per `##` heading. The search returns whole headings, so keep each one self-contained.
- No real carrier or client names, no rates, no passwords. Use codes (B1C06).
- Wrong knowledge is worse than none: the brain repeats it confidently. Review `learned/` regularly,
  move good notes into the right reviewed file, delete the rest.
- After editing files, restart the app (or POST http://127.0.0.1:8103/reindex) so the search sees the change.

## How it is stored
The files are the source of truth. On start, the knowledge tool splits them by heading and keeps a
full-text index in the brain database (table `brain.knowledge_chunk`). The index is rebuilt from the
files, so it can be dropped at any time.
