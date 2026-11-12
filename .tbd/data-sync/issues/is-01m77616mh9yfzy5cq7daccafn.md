---
type: is
id: is-01m77616mh9yfzy5cq7daccafn
title: "PR page: description final at first paint, body patched in place, commits with the record"
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m774rfn15h0t9ys9eg0nvgyx
parent_id: is-01m774q0ep0jq6vhb790rart0v
hold: null
hold_until: null
created_at: 2026-11-12T06:09:59.952Z
updated_at: 2026-11-12T07:24:35.653Z
started_at: 2026-11-12T06:11:47.012Z
---
From the page-header audit: Markdown description cached by record revision across mounts with a short hold for an in-flight request (never plain then Markdown); patch the Conversation body in place when the full record replaces the core preview; deliver commit rows with the record or never insert between painted cards; state from the fresher of catalog and cached record. Measured as body movement after first paint and no-input shift.

## Notes

Implemented on claude/perf-prpage (9bb4864e), draft PR #369. Accepted: late commit rows append at the end; first-visit description hold of up to 200 ms needs the exp-080 measurement against the earlier prepared-description readiness (71-80 ms). Awaiting exp-080.
