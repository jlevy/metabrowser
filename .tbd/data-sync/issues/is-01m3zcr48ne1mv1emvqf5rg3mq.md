---
type: is
id: is-01m3zcr48ne1mv1emvqf5rg3mq
title: Markdown and diff views each load one more module than 0.11.0; choose their loading tier from a measurement
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
created_at: 2026-10-02T22:46:21.716Z
updated_at: 2026-10-02T22:46:21.716Z
---
Browser differential (318 steps): /plugin-static/markdown/place-rendered.js is requested on every Markdown view and /plugin-static/diff/diff-view-file.js on every diff view; nothing visible changes and neither has a CHANGELOG line. diff-view-file.js serves the mirror-only View file control, so a regular folder may not need it at all. Measure the cost and pick eager, prefetched or on demand per AGENTS.md asset loading tiers; add the CHANGELOG line if they stay.
