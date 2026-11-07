---
type: is
id: is-01m6shhp93hj2aybfj68g5prxh
title: Verify PR watch updates, disconnects, and reconnects
kind: task
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/active/plan-2026-11-06-pr-watch-and-reconnect.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m6shhkwxasd5rpv91y17qc4w
hold: null
hold_until: null
created_at: 2026-11-06T23:01:52.546Z
updated_at: 2026-11-07T04:26:49.229Z
started_at: 2026-11-06T23:03:25.395Z
closed_at: 2026-11-07T04:26:49.228Z
close_reason: "PR #312 exact reviewed head is green in CI. Checkout and managed sessions cover updates, provider-only and server outages, reconnect, missing gh, slow retries and cached use. The opt-in real-gh PR list test also passed."
resolution: null
duplicate_of: null
---
Verify new and edited PRs and status changes, disconnected and restored networking, absent or unauthenticated gh, rate limiting, and cached use in both source modes with focused sessions and a manual browser playbook.

## Notes

Verified checkout, managed repository, missing gh, provider-only outage recovery, local-server recovery, and new/retitled/closed catalog entries. Slow-provider test showed the same visible and live outage text while Reload was disabled and spinner active, then restored Reload. Exact reviewed stack verification running.
