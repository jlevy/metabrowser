---
type: is
id: is-01m8d1tgm8sqfmbrkrhevn8265
title: "Record which lane each gh call served: visible, attended, prefetch, background"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8bmw4sdejvn3fx7tjgeyvpz
hold: null
hold_until: null
created_at: 2026-11-26T23:07:34.920Z
updated_at: 2026-11-27T00:05:10.116Z
started_at: 2026-11-27T00:05:10.116Z
---
The plan's request report groups by lane, but no gh call records which lane it served; mb-e2qx reports budget (reader, automatic, speculative, walk) and job instead and lists lanes as unrecorded. Record the lane at the source, as gh_budget.current_budget is recorded, so the report and the browsing benchmark (mb-ulvg) can hold visible work ahead of background work.
