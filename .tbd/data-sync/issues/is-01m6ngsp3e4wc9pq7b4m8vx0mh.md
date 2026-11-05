---
type: is
id: is-01m6ngsp3e4wc9pq7b4m8vx0mh
title: "PR #301 R3: Retry a busy live viewport at most once"
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6ngsms9m08a746a7fwhpprp
hold: null
hold_until: null
created_at: 2026-11-05T09:31:48.205Z
updated_at: 2026-11-05T09:31:49.577Z
started_at: 2026-11-05T09:31:49.576Z
---
Medium review at https://github.com/jlevy/metabrowser/pull/301#discussion_r4478710011. Preserve competing ownership and avoid churn while still letting an unchanged busy viewport receive one retry.
