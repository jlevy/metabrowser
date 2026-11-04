---
type: is
id: is-01m2hrdmk40n34a85r702vwhxg
title: Keep the flat-stress budget file from drifting off the release gate
kind: task
status: closed
priority: 2
version: 5
delegate: claude-code@spud10.local
labels:
  - performance
dependencies: []
parent_id: is-01m2hs64m7nfagfxyf7b0hxrhr
hold: null
hold_until: null
created_at: 2026-09-15T05:25:17.028Z
updated_at: 2026-11-04T17:14:29.790Z
started_at: 2026-11-01T16:21:29.110Z
closed_at: 2026-11-04T17:14:29.790Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
`explorations/performance-loop/performance-budgets-flat-stress.toml` is the release
gate's file with one declared divergence (`first_row_ms` 350 -> 450). The loader takes no
inheritance, so it is a standalone copy, and nothing stops the two drifting apart.

Today the relationship is stated in the stress file's header and verified by hand.
AGENTS.md prefers a check to a sentence, so this should be a check: assert that the two
files' `[requirements]` tables are equal and that their `[metrics]` tables differ only in
the keys the stress file's header declares.

Done when: a check enforces it and fails on an undeclared divergence in either direction.

## Notes

2026-11-01: fixed in PR #276, open, CI green at its last read. Close when it merges; its required review has not run.
