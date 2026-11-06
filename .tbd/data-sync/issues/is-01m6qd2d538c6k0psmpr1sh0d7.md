---
type: is
id: is-01m6qd2d538c6k0psmpr1sh0d7
title: Automatically fill the PR cache from a visible direct link
kind: bug
status: closed
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-06T03:05:08.515Z
updated_at: 2026-11-06T04:24:46.230Z
started_at: 2026-11-06T03:05:09.001Z
closed_at: 2026-11-06T04:24:46.229Z
close_reason: "Completed and verified in PR #307."
resolution: null
duplicate_of: null
---
A direct browser PR route on a running server should read persisted metadata first and automatically fill a truly cold cache once when visible. Preserve the selected-fetch budget, actionable prior failures, explicit comparison acquisition on checkouts, and stale-while-refresh behavior.

## Notes

Implemented in stacked PR #307 above #306 at 122af86c. Visible cold links reuse the bounded selected fetch after the disk read. Both source modes saved owner-only JSON. The built-in browser reopened a saved record after restarting with gh disabled and showed a stale record before a newer one was published. Browserless goldens cover hidden pages, warm hits, and explicit recovery after failure. Exact-head make verify passed with 4,855 tests and 381 transcript checks. All nine checks passed in GitHub run 42160936907, with zero unresolved review findings.
