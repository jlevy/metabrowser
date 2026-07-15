---
type: is
id: is-01kxhrcrsva75d74v2ejc8560w
title: "PR #1 review R5: degrade corrupt gzip file probes"
kind: bug
status: closed
priority: 1
version: 4
labels:
  - pr-review
  - metabrowser
dependencies: []
parent_id: is-01kxhpk3s4ffm69y00gc20pccg
created_at: 2026-07-15T02:06:19.450Z
updated_at: 2026-07-15T02:21:50.960Z
closed_at: 2026-07-15T02:21:50.960Z
close_reason: "Resolved on MetaBrowser PR #1 with red-first regression coverage, complete local verification, per-thread replies, and thread resolution. Latest head dfcd83e has all repository checks green and no unresolved review threads."
---
Resolve review thread PRRT_kwDOTX174c6Q9F9w at src/metabrowser/server.py:1114. /api/file must catch ArtifactPath size-probe failures for corrupt or truncated gzip files and return its binary degradation envelope instead of the generic internal-error path.

## Notes

Red regression confirmed a two-byte .txt.gz reached api_file's generic internal-error envelope because logical_size raised before the read fallback. Split gzip identity fields from trailer-dependent size metadata and catch size-probe failures into the binary degradation contract. Focused file/gzip slice: 12 passed. Complete make verify: 625 tests and all package gates passed.
