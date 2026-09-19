---
type: is
id: is-01m2wbxg2pb42nj7zacndrsvsc
title: QA runbook for v0.11 Repository Library and HTML-trust
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/qa-v011-repository-library.md
delegate: unknown@cursor
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-19T08:18:23.957Z
updated_at: 2026-09-19T08:23:46.122Z
started_at: 2026-09-19T08:18:28.015Z
closed_at: 2026-09-19T08:23:46.122Z
close_reason: "Runbook is in docs/qa-v011-repository-library.md; empty-home below-floor refuse no longer writes f01; QA steps executed on #214 tip plus #209 worktree."
resolution: null
duplicate_of: null
---
Write and execute docs/qa-v011-repository-library.md against the #214 Git-pin tip and a #209 HTML worktree. Isolate METABROWSER_HOME. Do not serve acquired Git. Do not merge. File child beads only for real defects. Close only when the runbook is in the tree, the executable steps have been run, and results are recorded.
