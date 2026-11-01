---
type: is
id: is-01m3zcr48ne1mv1emvqf5rg3mq
title: Markdown and diff views each load one more module than 0.11.0; choose their loading tier from a measurement
kind: task
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
created_at: 2026-10-02T22:46:21.716Z
updated_at: 2026-11-01T17:59:58.219Z
started_at: 2026-11-01T16:21:32.028Z
---
Browser differential (318 steps): /plugin-static/markdown/place-rendered.js is requested on every Markdown view and /plugin-static/diff/diff-view-file.js on every diff view; nothing visible changes and neither has a CHANGELOG line. diff-view-file.js serves the mirror-only View file control, so a regular folder may not need it at all. Measure the cost and pick eager, prefetched or on demand per AGENTS.md asset loading tiers; add the CHANGELOG line if they stay.

## Notes

2026-11-01: fixed in PR #277, open, CI green at its last read. Close when it merges; its required review has not run.
