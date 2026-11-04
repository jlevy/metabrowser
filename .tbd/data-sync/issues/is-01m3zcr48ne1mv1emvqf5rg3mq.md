---
type: is
id: is-01m3zcr48ne1mv1emvqf5rg3mq
title: Markdown and diff views each load one more module than 0.11.0; choose their loading tier from a measurement
kind: task
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
created_at: 2026-10-02T22:46:21.716Z
updated_at: 2026-11-04T17:14:29.773Z
started_at: 2026-11-01T16:21:32.028Z
closed_at: 2026-11-04T17:14:29.773Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Browser differential (318 steps): /plugin-static/markdown/place-rendered.js is requested on every Markdown view and /plugin-static/diff/diff-view-file.js on every diff view; nothing visible changes and neither has a CHANGELOG line. diff-view-file.js serves the mirror-only View file control, so a regular folder may not need it at all. Measure the cost and pick eager, prefetched or on demand per AGENTS.md asset loading tiers; add the CHANGELOG line if they stay.

## Notes

2026-11-01: fixed in PR #277, open, CI green at its last read. Close when it merges; its required review has not run.
