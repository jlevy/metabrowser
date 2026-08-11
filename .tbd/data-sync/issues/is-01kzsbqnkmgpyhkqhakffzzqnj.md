---
type: is
id: is-01kzsbqnkmgpyhkqhakffzzqnj
title: "PR #24 review R15: log page cursor carries an unbounded --skip"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies: []
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-11T21:30:24.243Z
updated_at: 2026-08-11T21:30:47.720Z
closed_at: 2026-08-11T21:30:47.719Z
close_reason: Fixed on feat/git-graph-view; covered by tests that fail without the fix.
---
Malformed cursors were rejected, but any well-formed cursor could carry an arbitrarily large skip that went straight to git log --skip, which walks and discards the whole prefix. One request could spend the full subprocess timeout budget to return nothing. Fixed with GIT_LOG_MAX_SKIP (100_000, ~400 pages at the default limit); decode_cursor rejects anything past it, so the route answers 400 like any other unusable cursor.
