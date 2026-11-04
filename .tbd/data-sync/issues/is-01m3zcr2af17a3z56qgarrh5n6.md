---
type: is
id: is-01m3zcr2af17a3z56qgarrh5n6
title: JSONL log event rows are not keyboard-focusable and lost their clickable accessibility node
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
created_at: 2026-10-02T22:46:19.726Z
updated_at: 2026-11-04T17:14:29.761Z
started_at: 2026-11-01T16:05:49.042Z
closed_at: 2026-11-04T17:14:29.761Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Browser differential: 0.11.0 exposed each JSONL log header row as a clickable generic container in the accessibility tree; after inline handlers were removed (delegated controls, SDK 0.7) the stack exposes only the icon and text. Rows still respond to a pointer click. Neither build makes them keyboard-focusable. Give the rows a real control role, a tab stop and Enter/Space handling, with a browserless interaction test.

## Notes

2026-11-01: fixed in PR #275, open, CI green at its last read. Close when it merges; its required review has not run.
