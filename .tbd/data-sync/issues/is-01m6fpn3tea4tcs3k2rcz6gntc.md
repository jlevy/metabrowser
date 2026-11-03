---
type: is
id: is-01m6fpn3tea4tcs3k2rcz6gntc
title: "PR #281 D7: in the refused state every ask after the mirror's fetch ended fetches the mirror again"
kind: bug
status: in_progress
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fpn0yb9yn4kakx1qp787e4
hold: null
hold_until: null
created_at: 2026-11-03T03:18:43.277Z
updated_at: 2026-11-03T03:50:30.986Z
started_at: 2026-11-03T03:50:30.985Z
---
Suggestion. src/metabrowser/mirror_refresh.py:1114. Fix: when seen.pull_job_refused and a mirror refresh ended since the miss, re-ask only the companion job. Review: https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5746822976 (PR #281, head 7bef1356).
