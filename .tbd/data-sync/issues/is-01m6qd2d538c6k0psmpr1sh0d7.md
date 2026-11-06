---
type: is
id: is-01m6qd2d538c6k0psmpr1sh0d7
title: Automatically fill the PR cache from a visible direct link
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-06T03:05:08.515Z
updated_at: 2026-11-06T03:10:33.678Z
started_at: 2026-11-06T03:05:09.001Z
---
A direct browser PR route on a running server should read persisted metadata first and automatically fill a truly cold cache once when visible. Preserve the selected-fetch budget, actionable prior failures, explicit comparison acquisition on checkouts, and stale-while-refresh behavior.

## Notes

Implemented on bf37a0fe above PR #306. Visible cold links reuse the bounded selected fetch after the disk read. Both source modes saved owner-only JSON. The built-in browser reopened that record after restarting with gh disabled and showed a stale record before a newer record was published. Browserless goldens cover hidden pages, warm hits and explicit recovery after a failed fetch. Full verification is running.
