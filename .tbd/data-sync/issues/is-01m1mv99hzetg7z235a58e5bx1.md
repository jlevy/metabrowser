---
type: is
id: is-01m1mv99hzetg7z235a58e5bx1
title: "PR #101 R5e: the validator equivalence corpus is not committed"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:21.854Z
updated_at: 2026-09-04T02:07:14.329Z
closed_at: 2026-09-04T02:07:14.328Z
close_reason: Fixed on claude/inventory-engine-perf; make verify green.
resolution: null
duplicate_of: null
---
The 10,180-input equivalence corpus that justifies the require_canonical_inventory_path rewrite is not in the tree, so make verify cannot notice a later edit breaking equivalence. Committed cases also leave a trailing empty segment ('a/', 'a//') and the non-ASCII accept case ('cafe/naive.txt') unpinned.
