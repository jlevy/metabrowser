---
type: is
id: is-01m7h0xeg94fbfbegjkh48g7ae
title: "PR #455 B2: on the app's start the store holds identity bytes the app's window asks for about once per server"
kind: bug
status: open
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7h0wnsjyz9enemj0de4q5wg
hold: null
hold_until: null
created_at: 2026-11-16T01:52:58.376Z
updated_at: 2026-11-16T02:08:49.845Z
started_at: 2026-11-16T01:53:15.183Z
---
Severity: Medium. PR #455 (https://github.com/jlevy/metabrowser/pull/455), review B (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914011305), finding B2. References: src/metabrowser/delivery.py:138-142; src/metabrowser/encoded_assets.py:91-101, :163-179.

## Notes

Deferred from PR #455 review B, B2 (https://github.com/jlevy/metabrowser/pull/455#pullrequestreview-5914011305). Waits on exp-095's verdict on H115 (a) (mb-9uyq), and on its no-store arm (B12) in particular: the coordinator decided #455 does not change what the store holds. If the store stays, pick between keeping nothing when the process serves locally (read in a thread, check the digest, send) and A11's gzip-only store (mb-0i10). Protocol: docs/project/specs/active/plan-2026-08-21-load-time-performance.md, The exp-095 Protocol for H115.
