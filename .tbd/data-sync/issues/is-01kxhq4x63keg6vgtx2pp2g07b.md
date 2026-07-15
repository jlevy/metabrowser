---
type: is
id: is-01kxhq4x63keg6vgtx2pp2g07b
title: "PR #1 review R2: chunk gzip text reads"
kind: bug
status: closed
priority: 1
version: 4
labels:
  - pr-review
  - metabrowser
dependencies: []
parent_id: is-01kxhpk3s4ffm69y00gc20pccg
created_at: 2026-07-15T01:44:33.219Z
updated_at: 2026-07-15T02:21:50.930Z
closed_at: 2026-07-15T02:21:50.930Z
close_reason: "Resolved on MetaBrowser PR #1 with red-first regression coverage, complete local verification, per-thread replies, and thread resolution. Latest head dfcd83e has all repository checks green and no unresolved review threads."
---
Resolve review thread PRRT_kwDOTX174c6Q843x at src/metabrowser/server.py:1216. The /api/file text branch must apply logical-byte offset/limit chunking to gzip artifacts without materializing the whole decompressed file, while preserving the plain-text response contract.

## Notes

Red regression reproduced the review finding: a gzip request for logical bytes 117..159 returned the complete decompressed payload. Implemented a gzip-transparent bounded binary-window helper and routed both plain and gzip previews through it off the event loop. Focused endpoint/gzip slice: 11 passed. Complete make verify under the repository-required Node 24.18.0/npm 11.16.0: 620 tests, Ruff/BasedPyright/Biome/TypeScript/Flowmark/public hygiene clean, npm and uv audits clean, wheel/sdist build and isolated install checks passed.
