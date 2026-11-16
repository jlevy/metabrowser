---
type: is
id: is-01m7hgpc9550w78kmwqsvv64xh
title: "Release 0.13: prepare the PyPI package and macOS app release (owner asked 2026-11-15)"
kind: epic
status: open
priority: 1
version: 9
labels: []
dependencies: []
child_order_hints:
  - is-01m7hhr1qbg4f07e1scdq20d7n
  - is-01m7hhr29ft7vypdg5eaz0md2s
  - is-01m7hhr2r1bmm0ve8a6qs5nnqw
  - is-01m7hhr36mmrjwfw662gmgngf6
  - is-01m7hhr3n6wpvfm1zpsxjh210t
  - is-01m7hhr43k5rc7ytbxg1vx031s
created_at: 2026-11-16T06:28:43.940Z
updated_at: 2026-11-16T15:09:28.698Z
---
Owner: "and go through the thoroough process to prepare a release of macos and metabrowser app". Follow docs/publishing.md and apps/macos/README.md: land stacks #446 and #454, make verify, previous-release performance comparison, release-prep record, version, notes, owner approval of exact commit and notes, then publish.

## Notes

Plan: attic/coord/release-plan-0.13.md in the coordinator worktree. Owner decisions 2026-11-16: package 0.13.0 and app 0.1.0 (raise the app's floor to 0.13.0 after the v0.13.0 tag); ship the app as an alpha despite the WebKit gate (mb-gvtw), listing the limitation; #453 is fixed and landed with the docs stack; the 0.12 follow-ups (mb-m20f, mb-etqi, mb-2g6f) do not gate 0.13 and are recorded as deferred. Blockers needing the owner: disk (5.9 GiB free; need about 25 GB), Low Power Mode on, Developer ID identity present but not valid (G2 intermediate missing), no notary profile.
