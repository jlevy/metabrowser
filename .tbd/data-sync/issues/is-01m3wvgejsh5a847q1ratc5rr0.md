---
type: is
id: is-01m3wvgejsh5a847q1ratc5rr0
title: A Git pin reads a compound-name JSONL file as text where a folder parses it as JSONL
kind: bug
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T23:06:35.471Z
updated_at: 2026-11-01T17:59:46.965Z
started_at: 2026-11-01T16:05:45.980Z
---
Found while fixing the hover prefetch (PR #264): on a pin, /api/file compares the compound extension tail with '.jsonl', so 'run.codex.jsonl' is read as text, where a served folder parses the same file as JSONL events. Pins are unreleased, so this is not a regression; make the pin's kind selection agree with the folder's for compound names, with a test in the source-agreement suite. Also from that PR, in explorations/performance-loop: startup_pairs.py appends to --out and restarts pair numbers at 0, so summarize silently keeps only the last run's rows for a pair number (fix or refuse); the README says compare_builds' first_row runs from spawn while the code counts from the first answered request; report.md's exp-037 row shows the uncached figures with no state marker.

## Notes

2026-11-01: fixed in PR #274, open, CI green at its last read. Close when it merges; its required review has not run.
