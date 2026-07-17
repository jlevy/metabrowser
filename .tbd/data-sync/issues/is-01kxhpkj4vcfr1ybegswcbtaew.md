---
type: is
id: is-01kxhpkj4vcfr1ybegswcbtaew
title: "PR #1 review R1: load dotenv before direct server discovery"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kxhpk3s4ffm69y00gc20pccg
created_at: 2026-07-15T01:35:04.859Z
updated_at: 2026-07-15T02:21:50.914Z
closed_at: 2026-07-15T02:21:50.913Z
close_reason: "Resolved on MetaBrowser PR #1 with red-first regression coverage, complete local verification, per-thread replies, and thread resolution. Latest head dfcd83e has all repository checks green and no unresolved review threads."
---
Cursor medium finding on PR #1 thread PRRT_kwDOTX174c6Q8ze7 at src/metabrowser/server.py:1716: direct imports such as uvicorn metabrowser.server:app do not call load_dotenv_chain before one-shot plugin discovery, so METABROWSER_PLUGINS_DIRS set only in .env or .env.local is skipped. Add regression coverage and preserve test-collection isolation.
