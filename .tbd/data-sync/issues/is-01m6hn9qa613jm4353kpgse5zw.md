---
type: is
id: is-01m6hn9qa613jm4353kpgse5zw
title: Preserve catalog rate holds across concurrent page publications
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:33:30.304Z
updated_at: 2026-11-03T21:42:59.745Z
started_at: 2026-11-03T21:34:50.490Z
---
Independent backend review reproduced two catalog workers sharing a source: one receives a rate hold, while the other publishes an already-in-flight valid page and overwrites the saved hold, then makes two more provider calls before reset. Preserve the network deadline independently of successful metadata publication, check it at actual provider boundaries, and add/recheck the unchanged independent multiworker probe. Initial review artifacts catalog-backend-review-ea771741.

## Notes

2026-11-03 fix checkpoint: canonical catalog outcome writes now preserve an unexpired shared reset under the source-alias lock; disk and memory holds are combined. Each page rechecks the hold after waiting for its network slot, and async stamp publishers use run_lock_section so canceled waiters cannot publish late. Permanent overlap/outcome/cancellation regressions added. Unchanged independent rate-hold probe passes; final independent review remains pending.
