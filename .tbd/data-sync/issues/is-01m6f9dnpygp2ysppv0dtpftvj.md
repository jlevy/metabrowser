---
type: is
id: is-01m6f9dnpygp2ysppv0dtpftvj
title: A list's refresh waits behind queued pull-request jobs
kind: task
status: closed
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f39wqb7nqd20w7z5vpw9vh
created_at: 2026-11-02T23:27:27.965Z
updated_at: 2026-11-03T02:16:41.906Z
closed_at: 2026-11-03T02:16:41.905Z
close_reason: "Resolved by PR 281's A1 fix (8f5957dd): a store job takes its slot only once its turn comes, so a list refresh no longer waits behind queued pull-request jobs; test_a_job_waiting_its_turn_holds_no_slot_so_a_list_refresh_starts_at_once. A list now waits only while both slots are in use."
resolution: null
duplicate_of: null
---
RefreshCoordinator's semaphore is first come, first served, and a pull-request job takes a slot before its turn at the store. With MAX_PULL_JOBS queued, one holds a slot and the turn, another holds a slot waiting for the turn, and a list refresh (which needs no turn) waits behind all of them: up to about 40 s by the times measured on pallets/click. Step 3 should measure whether the tab's first list feels this, and if so take the turn before the slot, keeping the mirror's job safe from a lock-order inversion, or give lists a slot of their own.
