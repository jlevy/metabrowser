---
type: is
id: is-01m7vnr99dgq5qyfbj40warset
title: "Main red: source-freshness golden pins /api/event-logs to a stale commit after #629 and #632 merged"
kind: bug
status: in_progress
priority: 0
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T05:09:33.612Z
updated_at: 2026-11-20T05:12:16.129Z
started_at: 2026-11-20T05:09:36.454Z
---
Main run 44676764477 (merge of #632 at f61159ade) fails tests/golden/cli-ui-source-freshness.tryscript.md on all four "goldens and serial" jobs.

Cause: a semantic merge conflict, deterministic, not a flake. #629 added "/api/event-logs" (a lookalike the pin guard must still guard) to the guard step of tests/dom/source-freshness-session.js and blessed its golden line with the then-current page pin 42382ea. #632 (branch did not contain #629) re-recorded tests/fixtures/source-freshness-responses.json so recorded.refreshed.pin, the pin the guarded fetch names, became 66f65bf, and re-blessed every pin in the golden. The two edits touch adjacent lines, so git merged them without a conflict and left the new line on the old hash. A branch with either PR but not both passes.

Fix: the code is right (the guard names the page's pin on /api/event-logs; tests/test_checkout_revisions.py asserts the server answers it 409). Correct the one golden line to 66f65bf.

## Notes

PR #638 (head 1fb9caf33): one golden line, /api/event-logs pin 42382ea -> 66f65bf. Awaiting CI.
