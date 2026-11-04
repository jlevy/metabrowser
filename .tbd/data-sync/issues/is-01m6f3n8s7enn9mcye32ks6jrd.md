---
type: is
id: is-01m6f3n8s7enn9mcye32ks6jrd
title: A large repository is refused its first clone at a limit below what fits
kind: bug
status: closed
priority: 1
version: 4
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-02T21:46:45.414Z
updated_at: 2026-11-04T17:14:29.566Z
started_at: 2026-11-02T21:47:04.202Z
closed_at: 2026-11-04T17:14:29.566Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Fixed in 2b079c18 on claude/v012-pr-review-workflows: limit 1,350,000 KB with the measurement beside it (a 1.2 GB clone took 185 s against a 900 s deadline), METABROWSER_MAX_FIRST_CLONE_KB override, and a refusal saying what to do. Verified: a real first clone starts with progress at the default limit. Close when it merges.

## Notes

2026-11-03: fixed on PR 280 (2b079c18), reviewed in round 1 (A, B, C), CI green at 996ea90d. Closes when the stack merges.
