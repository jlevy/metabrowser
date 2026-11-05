---
type: is
id: is-01m6n5xwntvy5fmqtrewb5kp9z
title: Revoke a selected PR preview before persisting a failed attempt
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-prefetch
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
created_at: 2026-11-05T06:21:51.673Z
updated_at: 2026-11-05T07:18:59.365Z
closed_at: 2026-11-05T07:18:59.365Z
close_reason: "Implemented or diagnosed in Metabrowser PR #299 at 0d1b132d. Independent review, paired evidence, local make verify and all nine GitHub CI jobs passed; PR is mergeable. Merge remains with the owner."
resolution: null
duplicate_of: null
---
If the final account check rejects a staged core, a pending GET could still serve it while the failure stamp writes. Hold that write in the existing account-change session, require revocation before it begins, and keep the full record untouched.

## Notes

Held failure-stamp persistence reproduces the account exposure; clearing provisional core before the write passed 24 selected/core tests. Included in 0d1b132d; full verification running.
