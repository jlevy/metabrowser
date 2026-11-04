---
type: is
id: is-01m6hn9qa613jm4353kpgse5zw
title: Preserve catalog rate holds across concurrent page publications
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:33:30.304Z
updated_at: 2026-11-04T17:14:29.687Z
started_at: 2026-11-03T21:34:50.490Z
closed_at: 2026-11-04T17:14:29.687Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Independent backend review reproduced two catalog workers sharing a source: one receives a rate hold, while the other publishes an already-in-flight valid page and overwrites the saved hold, then makes two more provider calls before reset. Preserve the network deadline independently of successful metadata publication, check it at actual provider boundaries, and add/recheck the unchanged independent multiworker probe. Initial review artifacts catalog-backend-review-ea771741.

## Notes

2026-11-03 fix checkpoint: canonical catalog outcome writes now preserve an unexpired shared reset under the source-alias lock; disk and memory holds are combined. Each page rechecks the hold after waiting for its network slot, and async stamp publishers use run_lock_section so canceled waiters cannot publish late. Permanent overlap/outcome/cancellation regressions added. Unchanged independent rate-hold probe passes; final independent review remains pending.
