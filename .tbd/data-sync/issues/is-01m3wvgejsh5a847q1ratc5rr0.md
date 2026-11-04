---
type: is
id: is-01m3wvgejsh5a847q1ratc5rr0
title: A Git pin reads a compound-name JSONL file as text where a folder parses it as JSONL
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
created_at: 2026-10-01T23:06:35.471Z
updated_at: 2026-11-04T17:14:29.605Z
started_at: 2026-11-01T16:05:45.980Z
closed_at: 2026-11-04T17:14:29.605Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Found while fixing the hover prefetch (PR #264): on a pin, /api/file compares the compound extension tail with '.jsonl', so 'run.codex.jsonl' is read as text, where a served folder parses the same file as JSONL events. Pins are unreleased, so this is not a regression; make the pin's kind selection agree with the folder's for compound names, with a test in the source-agreement suite. Also from that PR, in explorations/performance-loop: startup_pairs.py appends to --out and restarts pair numbers at 0, so summarize silently keeps only the last run's rows for a pair number (fix or refuse); the README says compare_builds' first_row runs from spawn while the code counts from the first answered request; report.md's exp-037 row shows the uncached figures with no state marker.

## Notes

2026-11-01: fixed in PR #274, open, CI green at its last read. Close when it merges; its required review has not run.
