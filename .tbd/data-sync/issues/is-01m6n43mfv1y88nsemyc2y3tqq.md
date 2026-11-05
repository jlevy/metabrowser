---
type: is
id: is-01m6n43mfv1y88nsemyc2y3tqq
title: Show PR loading blocks on the first selection from the Pulls landing
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-prefetch
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T05:50:02.746Z
updated_at: 2026-11-05T06:21:52.304Z
started_at: 2026-11-05T05:52:22.802Z
---
The neutral Pulls landing prompt lives inside a plugin host, so the preview owner treats it as useful retained content and hides the first PR’s loading blocks in an inert stage. Mark the neutral host explicitly, preserve real prior views, and add a focused source session plus manual first-selection verification. Keep the unchanged startup script limit.

## Notes

Neutral landing is marked empty. Held-request and installed-browser sessions pass: accessible gray blocks replace the neutral pane and then yield to the full Conversation. The UI golden now paints the pending state once. Included in 0d1b132d; full verification running.
