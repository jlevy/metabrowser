---
type: is
id: is-01m2ysbv6e26vngv7ygqgqx2bj
title: "PR 216 R2: refuse symlink targets traversing above the Git root"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m2yryd6had8zdvj8eag4a4v4
hold: null
hold_until: null
created_at: 2026-09-20T06:51:54.445Z
updated_at: 2026-09-20T07:15:19.701Z
started_at: 2026-09-20T06:53:09.013Z
closed_at: 2026-09-20T07:15:19.699Z
close_reason: "Fixed in bc8dd72b: _git_symlink_target refuses parent traversal at the Git root."
resolution: null
duplicate_of: null
---
src/metabrowser/git/content_routes.py _git_symlink_target clamps parent at root. Reproduced root link ../file.txt incorrectly resolving to root file.txt. Reject traversal above root and test content endpoints.
