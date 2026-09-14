---
type: is
id: is-01m1apk7r12pzwp9rn36p9w4d0
title: "PR #90 P90-17: The full help is pinned twice"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:23:00.480Z
updated_at: 2026-09-14T07:01:00.191Z
closed_at: 2026-09-14T07:01:00.190Z
close_reason: "Fixed in PR #116: cli-surface pins the full --help once; the bare invocation test diffs its output against metab --help in the sandbox and asserts exit 0, printing only differing lines on a mismatch."
resolution: null
duplicate_of: null
---
cli-surface records roughly 170 duplicated lines for metab --help and the bare invocation.
