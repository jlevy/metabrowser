---
type: is
id: is-01m77616mh9yfzy5cq7daccafn
title: "PR page: description final at first paint, body patched in place, commits with the record"
kind: task
status: closed
priority: 1
version: 7
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
updated_at: 2026-11-13T16:39:09.421Z
started_at: 2026-11-12T06:11:47.012Z
closed_at: 2026-11-13T16:39:09.420Z
close_reason: "Landed in #369 (merge 597a7c70). exp-080 (H106) accepted: Conversation transitions whose description showed before its final form fell from 5 (5-7) to 1 (1-1), ranges apart, n=3 pairs. The predicted 0 was not reached: pulls.list_to_pr.cold still reads 1, likely the milestone firing on the hidden held description (inferred, not proven). Body movement after first paint was 0 in both builds."
resolution: null
duplicate_of: null
---
From the page-header audit: Markdown description cached by record revision across mounts with a short hold for an in-flight request (never plain then Markdown); patch the Conversation body in place when the full record replaces the core preview; deliver commit rows with the record or never insert between painted cards; state from the fresher of catalog and cached record. Measured as body movement after first paint and no-input shift.

## Notes

PR #369: 9484c273 makes the hold wait only for the description's Markdown (kept renders paint in the mount task; timeline read back to control timing; late commit rows append). Official exp-080 on the fixed harness.
