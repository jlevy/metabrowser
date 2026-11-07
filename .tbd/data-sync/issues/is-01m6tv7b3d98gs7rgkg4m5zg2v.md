---
type: is
id: is-01m6tv7b3d98gs7rgkg4m5zg2v
title: Restore focus when choosing a PR stack member
kind: task
status: in_progress
priority: 2
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6thd591bhgt6vp9v5ve0326
hold: null
hold_until: null
created_at: 2026-11-07T11:10:13.612Z
updated_at: 2026-11-07T11:10:14.087Z
started_at: 2026-11-07T11:10:14.086Z
---
Review of public pull request325 found keyboard focus can remain in the menu when it becomes hidden. Restore focus to a stable visible control/page destination without scrolling, and pin actual keyboard selection in the existing mount session. Evaluate the title-projection cost with evidence; missing titles array feedback is a same-build contract false positive because the server always emits aligned null fallbacks. No compatibility shim.
