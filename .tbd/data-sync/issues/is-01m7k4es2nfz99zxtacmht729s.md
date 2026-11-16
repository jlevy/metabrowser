---
type: is
id: is-01m7k4es2nfz99zxtacmht729s
title: "PR #481 A2: a focus repair no longer puts away a tooltip whose own anchor the rebuild removed"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7hdc0y0089a7fe07b2y7v6v
hold: null
hold_until: null
created_at: 2026-11-16T21:33:20.851Z
updated_at: 2026-11-16T21:33:28.538Z
started_at: 2026-11-16T21:33:28.537Z
---
Low. PR #481 review A (https://github.com/jlevy/metabrowser/pull/481#pullrequestreview-5928039255). src/metabrowser/static/app.js:3343-3345. The repair branch returns before looking at tooltipAnchor, so a tooltip on the replaced control stays up attached to a detached anchor. Fix: hide first when tooltipAnchor is disconnected; add the session case.
