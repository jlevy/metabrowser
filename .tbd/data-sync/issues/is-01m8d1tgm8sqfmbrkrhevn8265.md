---
type: is
id: is-01m8d1tgm8sqfmbrkrhevn8265
title: "Record which lane each gh call served: visible, attended, prefetch, background"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/914
    at: 2026-11-27T09:55:08.344Z
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m8bmw4sdejvn3fx7tjgeyvpz
hold: null
hold_until: null
created_at: 2026-11-26T23:07:34.920Z
updated_at: 2026-11-27T10:17:35.254Z
started_at: 2026-11-27T00:05:10.116Z
closed_at: 2026-11-27T10:17:35.254Z
close_reason: Merged to main as jlevy/metabrowser#914 (d0e0e1e9f). Live run against this repository recorded; the large public repository and mb-mg37's hour are left for the owner.
resolution: null
duplicate_of: null
---
The plan's request report groups by lane, but no gh call records which lane it served; mb-e2qx reports budget (reader, automatic, speculative, walk) and job instead and lists lanes as unrecorded. Record the lane at the source, as gh_budget.current_budget is recorded, so the report and the browsing benchmark (mb-ulvg) can hold visible work ahead of background work.
