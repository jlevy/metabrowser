---
type: is
id: is-01m6hp3w66pyvqttk9w3hbmj70
title: Reconcile removed historical PR rows in the incremental catalog
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
created_at: 2026-11-03T21:47:47.269Z
updated_at: 2026-11-03T21:47:47.269Z
---
The incremental catalog handles new PRs, edits, close/reopen, account changes and repository identity resets. An old PR that disappears from GitHub visibility is retained locally until disposable catalog rebuild: a total decrease alone cannot identify the missing row. Design a resumable full reconciliation before pruning missing rows, preserving updates/new PRs during the scan and cached offline data until confirmed. This is a documented nonblocking historical-deletion follow-up to mb-m13a, not a claim that incomplete scan absence proves deletion.
