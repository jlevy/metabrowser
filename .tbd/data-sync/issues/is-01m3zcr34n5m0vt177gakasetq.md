---
type: is
id: is-01m3zcr34n5m0vt177gakasetq
title: /view/.hidden/ shows 'Could not load file types.' and a skeleton that never finishes
kind: bug
status: closed
priority: 3
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-02T22:46:20.564Z
updated_at: 2026-11-04T17:14:29.534Z
started_at: 2026-11-01T16:05:48.708Z
closed_at: 2026-11-04T17:14:29.534Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Found by the browser differential; identical on 0.11.0 and the stack, so not a landing regression. Opening a dot-folder view leaves the overview skeleton unfinished with the error text. Decide whether a hidden folder is viewable and make the view either render or say why not.

## Notes

2026-11-01: fixed in PR #275, open, CI green at its last read. Close when it merges; its required review has not run.
