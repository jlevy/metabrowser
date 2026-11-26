---
type: is
id: is-01m8d1tffwxjb3n8tjt10m0ya5
title: Count a conditional read's 304 as answered, not failed, in the event log
kind: bug
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/906
    at: 2026-11-26T23:28:36.307Z
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8bmw4sdejvn3fx7tjgeyvpz
hold: null
hold_until: null
created_at: 2026-11-26T23:07:33.756Z
updated_at: 2026-11-26T23:28:36.308Z
started_at: 2026-11-26T23:28:35.405Z
---
gh api exits 1 on an HTTP 304, so every conditional probe GitHub answers unchanged ends its gh span 'failed' with failure 'exit', and /api/event-log/failures?kind=subprocess counts it ('gh: HTTP 304'): 7 of 8 failures in the request report's fixture. gh spans now carry http_status (mb-e2qx), so the span can end answered when the status is 304. Confirm against the real gh binary first.
