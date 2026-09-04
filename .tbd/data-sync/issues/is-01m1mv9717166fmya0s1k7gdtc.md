---
type: is
id: is-01m1mv9717166fmya0s1k7gdtc
title: "PR #101 R2b: one undecodable byte in a filename kills the whole index"
kind: bug
status: closed
priority: 0
version: 2
labels: []
dependencies: []
parent_id: is-01m1mv8fds3d80zj3qmg1cct9b
created_at: 2026-09-03T23:57:19.270Z
updated_at: 2026-09-04T02:07:12.122Z
closed_at: 2026-09-04T02:07:12.121Z
close_reason: Fixed on claude/inventory-engine-perf; make verify green.
resolution: null
duplicate_of: null
---
BLOCKER on POSIX/ext4 (not reproducible on macOS/APFS, which rejects such names with EILSEQ). walker.py:454,466 builds contract InventoryEntry straight from raw scandir names; __post_init__ -> require_canonical_inventory_path rejects surrogates; _run_walker's blanket handler marks discovery FAILED. Verified at the type boundary: InventoryEntry.for_observed_file(name='x\udcffy.txt') raises ValueError.
