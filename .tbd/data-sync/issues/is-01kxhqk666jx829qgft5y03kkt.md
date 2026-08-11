---
type: is
id: is-01kxhqk666jx829qgft5y03kkt
title: "PR #1 review R3: degrade malformed gzip KPress render"
kind: bug
status: closed
priority: 2
version: 4
labels:
  - pr-review
  - metabrowser
dependencies: []
parent_id: is-01kxhpk3s4ffm69y00gc20pccg
created_at: 2026-07-15T01:52:21.189Z
updated_at: 2026-07-15T02:21:50.939Z
closed_at: 2026-07-15T02:21:50.939Z
close_reason: "Resolved on MetaBrowser PR #1 with red-first regression coverage, complete local verification, per-thread replies, and thread resolution. Latest head dfcd83e has all repository checks green and no unresolved review threads."
---
Resolve review thread PRRT_kwDOTX174c6Q8-pW at src/metabrowser/server.py:1303. api_kpress_render must catch ArtifactPath size/read failures for malformed or truncated gzip sources and return an error response instead of surfacing an HTTP 500.

## Notes

Red regression reproduced the review finding: a two-byte truncated .md.gz raised OSError while reading the ISIZE trailer before api_kpress_render reached its read-error handler. Wrapped logical and disk size access in the route's existing 404 degradation contract. Focused KPress route/render slice: 26 passed. Complete make verify under Node 24.18.0: 621 tests, all Python/TypeScript/Markdown/public-hygiene gates clean, dependency audits clean, distribution build and isolated install checks passed.
