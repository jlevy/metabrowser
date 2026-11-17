---
type: is
id: is-01m7m8vbb7qh84gcfdrd70g7w7
title: A live change leaves a directory's mtime_ns at its discovered value
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T08:09:21.511Z
updated_at: 2026-11-17T08:09:21.511Z
---
The Python provider's live path (_update_ancestor_aggregates) moves a directory's newest_mtime_ns but not mtime_ns, which the contract defines as the same newest descendant regular-file time; the SSE record carries mtime_ns, so a browser can show a stale folder time. Recorded by the strict xfail test_a_live_change_moves_a_directory_mtime_with_its_newest_file (jlevy/metabrowser#508).
