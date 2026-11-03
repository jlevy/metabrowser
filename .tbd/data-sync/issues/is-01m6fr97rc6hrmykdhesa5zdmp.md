---
type: is
id: is-01m6fr97rc6hrmykdhesa5zdmp
title: "PR #284 D3: tests/test_git_process.py allowlist lacks GIT_ATTR_NOSYSTEM, failing test (3.12) and stack-integration"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fr829v5p0bx9wm4rr3z5wj
hold: null
hold_until: null
created_at: 2026-11-03T03:47:11.244Z
updated_at: 2026-11-03T03:53:09.262Z
started_at: 2026-11-03T03:47:30.598Z
closed_at: 2026-11-03T03:53:09.261Z
close_reason: |
  fixed in e610ebab: the allowlist carries GIT_ATTR_NOSYSTEM for every isolated policy, and GIT_ATTR_SOURCE on a store target for the store policies; tests/test_git_process.py passes.
resolution: null
duplicate_of: null
---
Medium. tests/test_git_process.py:97-104 spells each isolated policy's environment and was not updated when process.py:517 set GIT_ATTR_NOSYSTEM for every isolated policy; the layer above (#283) hit the same failure in its merge. Review D: https://github.com/jlevy/metabrowser/pull/284#pullrequestreview-5746804338. Fix: the allowlist carries GIT_ATTR_NOSYSTEM, and GIT_ATTR_SOURCE on a store target for the store policies.
