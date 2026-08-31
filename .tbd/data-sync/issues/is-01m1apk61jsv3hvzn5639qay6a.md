---
type: is
id: is-01m1apk61jsv3hvzn5639qay6a
title: "PR #90 P90-13: Literal percent-encoded filenames are ambiguous"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:58.736Z
updated_at: 2026-08-31T01:40:12.976Z
closed_at: 2026-08-31T01:40:12.976Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
unquote on the route means a file literally named %41.md cannot be addressed distinctly; undocumented.
