---
type: is
id: is-01ky071dz7zqcfxgxf97pc9vfn
title: "P3: retire the Recent tab behind the Recent preset"
kind: task
status: closed
priority: 2
version: 7
spec_path: null
labels: []
dependencies: []
parent_id: is-01ky070wk6z56ghjc9wyhf0sye
created_at: 2026-07-20T16:51:38.599Z
updated_at: 2026-11-04T17:14:27.806Z
closed_at: 2026-11-01T16:21:22.272Z
close_reason: e139acca folded Recent into Files; no tab-recent remains in src on main.
resolution: null
duplicate_of: null
extensions:
  linear:
    id: b81d0c3c-95f1-4942-bd2c-554169f43a57
    linked_at: 2026-08-16T08:06:38.766Z
---
Phase 3, gated on maintainer testing of Phases 1-2: run the parity checklist (clustering, counts, truncation marks, window switching, live updates, keyboard access) under the Recent preset against the live Recent tab, then retire the tab to a single Files pane with the filter bar. Explicitly a behavior change — do not start without maintainer sign-off.

## Notes

Tracking reconciliation: the structured spec_path `docs/project/specs/active/plan-2026-07-20-unified-filtering.md` does not exist in landed main da87bb13c4434324af576b554711278139621b6b. No exact surviving document or immutable historical blob has been established by this audit. Retire this broken structured pointer while preserving this completed task's status, description and implementation/review history. This note retains the former path for historical context; it does not claim that a current plan is the exact successor.
