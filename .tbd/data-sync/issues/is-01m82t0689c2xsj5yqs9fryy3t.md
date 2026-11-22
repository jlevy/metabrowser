---
type: is
id: is-01m82t0689c2xsj5yqs9fryy3t
title: Below BACKGROUND_FLOOR, a probe that answers 200 marks the record changed without starting its full read
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-22T23:38:27.974Z
updated_at: 2026-11-22T23:38:27.974Z
---
The plan's Budget section (docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md) keeps BACKGROUND_FLOOR for probes: they keep running, since a 304 is free, but a probe that finds a change below the floor marks the record changed and the page says it is behind and offers Refresh, instead of starting the full read. Not in PR #709; added to the Phase 1 checklist after review A9 (https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015073163).
