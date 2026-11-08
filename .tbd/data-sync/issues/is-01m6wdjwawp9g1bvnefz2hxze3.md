---
type: is
id: is-01m6wdjwawp9g1bvnefz2hxze3
title: Prepare the next Metabrowser release candidate without publishing
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m5wdbsy6z6d95sgg03kwmm76
hold: null
hold_until: null
created_at: 2026-11-08T01:50:20.508Z
updated_at: 2026-11-08T01:58:27.388Z
started_at: 2026-11-08T01:55:06.900Z
---
Coordinate the user's November 7 release-preparation request under existing release coordinator mb-4bd2; the decided version is 0.12.0, not a 0.11.1 patch. First finish and merge reviewed native stack302, then verify exact main, CI and installed wheel under mb-5k2w. Reuse the existing release-head data/evidence/browser differential tasks mb-2g6f and mb-8pyc, performance rehearsal mb-cf6y (five headed and five backend pairs on unchanged project-10, no concurrent heavy work), full QA mb-m20f and human sign-off mb-etqi. Refresh current docs/plans/skill, changelog, concise release notes and the behavior-change approval record; preserve failed or inconclusive results and name every remaining acceptance step honestly. No version tag, GitHub release, PyPI publication or post-publication success claim before explicit user approval. Prepare the concrete checklist and artifacts so approval is the final action before cutting the release.
