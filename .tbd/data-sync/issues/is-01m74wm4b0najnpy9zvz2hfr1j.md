---
type: is
id: is-01m74wm4b0najnpy9zvz2hfr1j
title: "PR #349 C1: each projection holds the GIL 25-75 ms in a worker thread; second load slot adds no throughput"
kind: bug
status: closed
priority: 2
version: 4
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74wk8dt7weq5cmkt2hmdrjr
hold: null
hold_until: null
created_at: 2026-11-11T08:47:05.566Z
updated_at: 2026-11-11T12:33:48.692Z
started_at: 2026-11-11T08:47:26.387Z
closed_at: 2026-11-11T12:33:48.691Z
close_reason: "C1 fixed in 04c0f235 and c448aae8: projection child process (65-70 MB RSS), thread until ready, one load at a time via _Slot, prewarm by the page's prefetch=1 requests. Measured 1.4 ms beside the child vs 32-35 ms beside a thread."
resolution: null
duplicate_of: null
---
Severity: High. PR #349 review: https://github.com/jlevy/metabrowser/pull/349#pullrequestreview-5855871513. References: pull_rendered_diff.py:104-111, 146-150. Addressed on PR #349 (branch codex/pr-rendered-markdown-diffs).

## Notes

Phase 1 (04c0f235): projections run in a long-lived child process (metabrowser.diff.markdown_projection_worker) once ready, thread until then; max_loads=1. Measured 8-wake request 1.41-1.42 ms beside the child vs 32-35 ms beside a thread. Open for phase 2: prewarm trigger when a PR page with Markdown changes mounts (needs pull-page.js or the comparison handler).
