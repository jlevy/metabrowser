---
type: is
id: is-01m7yp5eqs757h50kmqppqh1gp
title: Acquisition raises fetch_failed before reading the listing in which Git 2.56 refuses a case twin
kind: bug
status: closed
priority: 3
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/774
    at: 2026-11-24T00:47:09.074Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-21T09:14:28.472Z
updated_at: 2026-11-24T01:19:10.465Z
started_at: 2026-11-24T00:46:04.958Z
closed_at: 2026-11-24T01:19:10.464Z
close_reason: "Git 2.56.1 refuses a case twin in a non-atomic fetch (flag ! in --porcelain, exit 1) where 2.50.1 folded it and exited 0; acquisition raised FetchFailedError before reading that listing. GitCommandError now carries stdout and the fetch failure path reads the refused twin and raises RefCaseCollisionError from it: PR #774 (open, CI green, not merged)."
resolution: null
duplicate_of: null
---
On case-insensitive macOS APFS, Git 2.56.1 fetch exits 1 when two advertised refs differ only by case. Staging acquisition returns generic FetchFailedError before its post-fetch collision check can report ref_case_collision. The cache-resolve regression test reproduces the mismatch. A porcelain fetch of the same fixture succeeds with Apple Git 2.50.1 so the app can classify the collision, but Git 2.56.1 reports the collision and marks the second ref update failed. Map both supported Git behaviors to the same typed refusal without publishing incomplete refs.
