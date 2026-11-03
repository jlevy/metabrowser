---
type: is
id: is-01m6f3n8s7enn9mcye32ks6jrd
title: A large repository is refused its first clone at a limit below what fits
kind: bug
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:45.414Z
updated_at: 2026-11-03T07:00:47.039Z
started_at: 2026-11-02T21:47:04.202Z
---
Fixed in 2b079c18 on claude/v012-pr-review-workflows: limit 1,350,000 KB with the measurement beside it (a 1.2 GB clone took 185 s against a 900 s deadline), METABROWSER_MAX_FIRST_CLONE_KB override, and a refusal saying what to do. Verified: a real first clone starts with progress at the default limit. Close when it merges.

## Notes

2026-11-03: fixed on PR 280 (2b079c18), reviewed in round 1 (A, B, C), CI green at 996ea90d. Closes when the stack merges.
