---
type: is
id: is-01kzkv7nkq736a52pyye0dedvs
title: "PR #22 review R7: refetch cannot remove a deletion lost during the stream gap"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzkv76p2eprd181arkqfj0we
created_at: 2026-08-09T18:05:50.582Z
updated_at: 2026-08-09T18:21:04.121Z
closed_at: 2026-08-09T18:21:04.121Z
close_reason: "Fixed in 5f711b8; each has a regression test verified to fail without its fix. make verify green: 783 pytest, 28 golden, both TS configs, hygiene, supply chain, distribution."
---
catalog_feed.js:82-85, known_file_catalog.js:200-216. onSentinelSnapshot() refetches because deltas may have been dropped, but applyBulkSnapshot() only merges returned paths, so a file deleted during the gap and absent from the refetch stays searchable forever. Reviewer reproduced on 9b6baea. Fix: track the membership of the last authoritative feed snapshot and reconcile (replace/diff) on each successful 200, preserving only non-feed exceptions such as explicit navigation; replay buffered deltas after reconciliation. Needs per-path provenance rather than one overwritten source string.
