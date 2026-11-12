---
type: is
id: is-01m77616mh9yfzy5cq7daccafn
title: "PR page: description final at first paint, body patched in place, commits with the record"
kind: task
status: in_progress
priority: 1
version: 5
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
updated_at: 2026-11-12T10:08:35.778Z
started_at: 2026-11-12T06:11:47.012Z
---
From the page-header audit: Markdown description cached by record revision across mounts with a short hold for an in-flight request (never plain then Markdown); patch the Conversation body in place when the full record replaces the core preview; deliver commit rows with the record or never insert between painted cards; state from the fresher of catalog and cached record. Measured as body movement after first paint and no-input shift.

## Notes

Implemented on claude/perf-prpage (9bb4864e), PR #369. Pilot (harness v2, flawed timing): the 200 ms hold ran to its cap because of the cached_only timeline wait (cold list->PR 90 to 224 ms; revisit 28 to 211 ms), so the hold now waits only for the description's Markdown. Fix in progress; official exp-080 on the fixed harness.
