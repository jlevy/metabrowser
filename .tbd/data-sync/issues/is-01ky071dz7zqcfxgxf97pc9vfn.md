---
type: is
id: is-01ky071dz7zqcfxgxf97pc9vfn
title: "P3: retire the Recent tab behind the Recent preset"
kind: task
status: closed
priority: 2
version: 8
spec_path: null
labels: []
dependencies: []
parent_id: is-01ky070wk6z56ghjc9wyhf0sye
created_at: 2026-07-20T16:51:38.599Z
updated_at: 2026-11-20T19:15:57.850Z
closed_at: 2026-11-01T16:21:22.272Z
close_reason: e139acca folded Recent into Files; no tab-recent remains in src on main.
resolution: null
duplicate_of: null
extensions: {}
---
Phase 3, gated on maintainer testing of Phases 1-2: run the parity checklist (clustering, counts, truncation marks, window switching, live updates, keyboard access) under the Recent preset against the live Recent tab, then retire the tab to a single Files pane with the filter bar. Explicitly a behavior change — do not start without maintainer sign-off.

## Notes

Tracking reconciliation: the structured spec_path `docs/project/specs/active/plan-2026-07-20-unified-filtering.md` does not exist in landed main da87bb13c4434324af576b554711278139621b6b. No exact surviving document or immutable historical blob has been established by this audit. Retire this broken structured pointer while preserving this completed task's status, description and implementation/review history. This note retains the former path for historical context; it does not claim that a current plan is the exact successor.
