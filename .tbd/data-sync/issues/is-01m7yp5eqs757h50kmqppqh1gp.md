---
type: is
id: is-01m7yp5eqs757h50kmqppqh1gp
title: Preserve the typed case-collision refusal with Git 2.56 on macOS
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-21T09:14:28.472Z
updated_at: 2026-11-21T09:14:28.472Z
---
On case-insensitive macOS APFS, Git 2.56.1 fetch exits 1 when two advertised refs differ only by case. Staging acquisition returns generic FetchFailedError before its post-fetch collision check can report ref_case_collision. The cache-resolve regression test reproduces the mismatch. A porcelain fetch of the same fixture succeeds with Apple Git 2.50.1 so the app can classify the collision, but Git 2.56.1 reports the collision and marks the second ref update failed. Map both supported Git behaviors to the same typed refusal without publishing incomplete refs.
