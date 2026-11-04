---
type: is
id: is-01m6hxmmmtnemb4656ebq7c7h4
title: Show optional native stack membership and PR navigation
kind: feature
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: pulls_navigation
labels: []
dependencies: []
parent_id: is-01m6hx4w87z6r8ndnbt57avr53
hold: null
hold_until: null
created_at: 2026-11-03T23:59:16.631Z
updated_at: 2026-11-04T17:14:29.804Z
started_at: 2026-11-03T23:59:29.633Z
closed_at: 2026-11-04T17:14:29.804Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Frontend for the repository stack snapshot: authoritative native stack numbers, ordered member navigation and cached row badges, aligned with the reading column. Optional unknown/missing extension states omit enrichment without blocking cached catalog/detail. One shared snapshot, no per-row requests; preserve explicit user navigation, tab/history/focus and disposal ownership. Backend contract must be agreed before production writes. Independent UI review and current-source session/golden checks required.

## Notes

Writer handoff above a78ad4c5, no writer commit/push. Shared optional repository snapshot, one index/O(1) row lookup, source/reader guards, lazy ordered native disclosure, explicit-reader neighbors preserve tab/clear file; badges update existing row metadata without rebuilding focus/tree. Evidence stack-ui-a78ad4c5/frontend-final-handoff.json under durable agent evidence has reviewed and post-lint hashes.61 focused Python tests13.86s,7UI transcript cases, real-route recorder, both browser type gates, Ruff/Biome/parity/golden checks pass. Independent source review clean before equivalent final lint forms. Coordinator owns committed-byte reconciliation/full gate/publication/closure; exact final-wheel QA remains pending.
