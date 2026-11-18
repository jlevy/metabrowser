---
type: is
id: is-01m7pn8n0nyp1y7mj41d1b38wm
title: "Open modes: shared local-open resolver (walk-up, --exact-root, root in Serving line)"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T06:24:49.172Z
updated_at: 2026-11-18T06:24:49.172Z
---
Implement the one resolver arch-open-modes.md (#558) specifies: walk up to the nearest repository root with the owner's Q2(b) guards (not for an ignored path, not up to the home folder, not beyond loopback, serving only), --exact-root opt-out, the resolved root printed in the Serving line. #540's _resolve_local becomes this resolver; #539 and #546 route through it. Goldens and parity rows.
