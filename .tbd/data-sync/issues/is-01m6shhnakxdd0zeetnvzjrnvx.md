---
type: is
id: is-01m6shhnakxdd0zeetnvzjrnvx
title: Classify GitHub watch failures and bound catalog recovery
kind: task
status: closed
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-06-pr-watch-and-reconnect.md
delegate: codex@spud10.local
labels: []
dependencies:
  - type: blocks
    target: is-01m6shhp93hj2aybfj68g5prxh
parent_id: is-01m6shhkwxasd5rpv91y17qc4w
hold: null
hold_until: null
created_at: 2026-11-06T23:01:51.567Z
updated_at: 2026-11-07T02:19:05.649Z
started_at: 2026-11-06T23:03:25.375Z
closed_at: 2026-11-07T02:19:05.648Z
close_reason: "The reviewed watch backend is published in #312. Bounded incremental metadata refresh, network-only early reconnect, and normalized access and rate behavior passed provider and CLI sessions and live catalog smoke. Review follow-ups are confined to the status/filter UI."
resolution: null
duplicate_of: null
---
Reuse the shared catalog coordinator and incremental provider reads. Distinguish unreachable network, missing gh, sign-in, access, rate limits, and transient failures. Keep cache reads available and honor retry timing.
