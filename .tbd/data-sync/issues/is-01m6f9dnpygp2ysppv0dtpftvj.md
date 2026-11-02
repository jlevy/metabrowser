---
type: is
id: is-01m6f9dnpygp2ysppv0dtpftvj
title: A list's refresh waits behind queued pull-request jobs
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f39wqb7nqd20w7z5vpw9vh
created_at: 2026-11-02T23:27:27.965Z
updated_at: 2026-11-02T23:27:27.965Z
---
RefreshCoordinator's semaphore is first come, first served, and a pull-request job takes a slot before its turn at the store. With MAX_PULL_JOBS queued, one holds a slot and the turn, another holds a slot waiting for the turn, and a list refresh (which needs no turn) waits behind all of them: up to about 40 s by the times measured on pallets/click. Step 3 should measure whether the tab's first list feels this, and if so take the turn before the slot, keeping the mirror's job safe from a lock-order inversion, or give lists a slot of their own.
