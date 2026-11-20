---
type: is
id: is-01m7wy6srp11j8gvwqa11fmah5
title: "PR #656 A16: unterminated quote swallows rest of file (suggestion)"
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
created_at: 2026-11-20T16:56:32.278Z
updated_at: 2026-11-20T18:12:13.393Z
started_at: 2026-11-20T17:23:02.619Z
---
Severity Suggestion. PR #656 review A (https://github.com/jlevy/metabrowser/pull/656#pullrequestreview-5996326781). delimited parse.

## Notes

Deferred from PR #656 review A (A16). Waits on a design decision: how a page reports an unterminated quote (an envelope note or source_unreadable), and whether tab-separated text applies quoting. Python csv strict mode detects EOF inside quotes ('unexpected end of data') but also refuses data the lenient reader accepts.
