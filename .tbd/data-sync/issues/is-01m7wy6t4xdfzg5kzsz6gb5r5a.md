---
type: is
id: is-01m7wy6t4xdfzg5kzsz6gb5r5a
title: "PR #656 A17: protocol error for timed-out/busy work (suggestion)"
kind: bug
status: open
priority: 3
version: 4
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7wy6kbgkfyg4kf94bk8z11e
hold: null
hold_until: null
created_at: 2026-11-20T16:56:32.668Z
updated_at: 2026-11-20T18:12:13.692Z
started_at: 2026-11-20T17:23:02.955Z
---
Severity Suggestion. PR #656 review A (https://github.com/jlevy/metabrowser/pull/656#pullrequestreview-5996326781). table_source.py errors.

## Notes

Deferred from PR #656 review A (A17). Waits on Phase 4/5 (SQLite), the first source whose record/card can exhaust its budget or meet a locked database; add a TableSourceError subclass (budget or busy) with a code the table view handles, then.
