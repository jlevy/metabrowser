---
type: is
id: is-01m6wpgzn59yqd9ba9d3kae44m
title: Investigate an unreproduced PR-to-Commits loading stall in final-wheel QA
kind: bug
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m5wdbsy6z6d95sgg03kwmm76
parent_id: is-01m5wdbsy6z6d95sgg03kwmm76
hold: null
hold_until: null
created_at: 2026-11-08T04:26:35.547Z
updated_at: 2026-11-08T07:10:33.678Z
started_at: 2026-11-08T07:10:33.064Z
---
During source-preview UI acceptance at24f3721c9, one fresh /pull/327 -> Commits -> first history row changed URL to /commit/afaf38b85a83443e25002765203c216bd11f8dfa but left Loading commit with zero connected stages; tooltip independently had correct detail, direct local commit GET returned200 in78ms, and no console errors were captured. Direct reload then rendered correctly. A repeat of the same fresh PR-to-Commits sequence also rendered correctly. Cause and introduction are unestablished; do not claim a reproducible regression or add speculative compatibility/fallback code. Read-only independent audit found no confirmed delayed-landing claimant. During final installed-wheel QA, repeat cold and retained-preview handoffs; if it recurs capture preview-owner/pending-claim attrs, selected request settlement and source identity to distinguish pending detail, asset/comparison or stale navigation. Preserve failed observation separately from passing repetitions.
