---
type: is
id: is-01m82t0689c2xsj5yqs9fryy3t
title: Below BACKGROUND_FLOOR, a change a probe finds on the visible page still reads it; the 90 s full read and background work stop
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-22T23:38:27.974Z
updated_at: 2026-11-23T02:58:11.217Z
closed_at: 2026-11-23T02:58:11.215Z
close_reason: "Built in #726"
resolution: null
duplicate_of: null
---
The plan's Budget section (docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md) keeps BACKGROUND_FLOOR for probes: they keep running, since a 304 is free, but a probe that finds a change below the floor marks the record changed and the page says it is behind and offers Refresh, instead of starting the full read. Not in PR #709; added to the Phase 1 checklist after review A9 (https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015073163).

## Notes

Owner decision 2026-11-22 (answering #696 review A4): below BACKGROUND_FLOOR, a change a probe finds on the visible page still starts its full read; the FULL_REFRESH_S periodic full read and all background and prefetch work stop. This replaces the plan's earlier rule (a 200 below the floor only marks the record changed and offers Refresh).
