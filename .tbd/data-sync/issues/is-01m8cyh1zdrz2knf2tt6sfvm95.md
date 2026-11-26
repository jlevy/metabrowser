---
type: is
id: is-01m8cyh1zdrz2knf2tt6sfvm95
title: Let selected PR Conversation metadata run ahead of checkout acquisition
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/901
    at: 2026-11-26T22:37:13.436Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
hold: null
hold_until: null
created_at: 2026-11-26T22:09:59.272Z
updated_at: 2026-11-26T22:37:13.447Z
started_at: 2026-11-26T22:11:17.587Z
---
H126. Hold the checkout-store acquisition in a deterministic test. A selected pull should reach the exact visible Conversation core through existing provider validation before the Git gate releases. Guard viewer and source ownership, rate limiting, and the full record and Changes after acquisition.
