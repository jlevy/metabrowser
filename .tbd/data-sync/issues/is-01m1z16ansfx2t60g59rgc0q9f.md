---
type: is
id: is-01m1z16ansfx2t60g59rgc0q9f
title: Reject refresh hints through symlink ancestors
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m1z02d6kztqbb14m1cv9ny5q
created_at: 2026-09-07T22:53:00.472Z
updated_at: 2026-09-08T00:02:44.377Z
closed_at: 2026-09-08T00:02:44.375Z
close_reason: Refresh, priority hints, and subtree rewalk reject native symlink ancestors. Internal and outside-root link cases pass; visible leaf symlinks remain supported.
resolution: null
duplicate_of: null
---
The boot walker treats symlinks as leaves, but explicit file refresh lstat follows ancestor symlinks and may graft outside-root facts. Reproduce with both internal and external directory symlinks and share the no-follow scope guard with subtree rewalk.
