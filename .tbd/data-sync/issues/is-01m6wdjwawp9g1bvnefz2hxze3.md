---
type: is
id: is-01m6wdjwawp9g1bvnefz2hxze3
title: Prepare the next Metabrowser release candidate without publishing
kind: task
status: in_progress
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m5wdbsy6z6d95sgg03kwmm76
child_order_hints:
  - is-01m6wtacta0gcph1j42jw3vq26
  - is-01m6xby4qhb8m9fk5zd9x3tg5p
hold: null
hold_until: null
created_at: 2026-11-08T01:50:20.508Z
updated_at: 2026-11-08T10:40:46.832Z
started_at: 2026-11-08T01:55:06.900Z
---
Coordinate the user's November 7 release-preparation request under existing release coordinator mb-4bd2; the decided version is 0.12.0, not a 0.11.1 patch. First finish and merge reviewed native stack302, then verify exact main, CI and installed wheel under mb-5k2w. Reuse the existing release-head data/evidence/browser differential tasks mb-2g6f and mb-8pyc, performance rehearsal mb-cf6y (five headed and five backend pairs on unchanged project-10, no concurrent heavy work), full QA mb-m20f and human sign-off mb-etqi. Refresh current docs/plans/skill, changelog, concise release notes and the behavior-change approval record; preserve failed or inconclusive results and name every remaining acceptance step honestly. No version tag, GitHub release, PyPI publication or post-publication success claim before explicit user approval. Prepare the concrete checklist and artifacts so approval is the final action before cutting the release.

## Notes

November 7 UI checkpoint at 24f3721c9: shared bold normal-text-color actor/repository names; sidebar author/repo metadata12px, page actor/action/age14px; commit history/page/tooltip migrated. Stack list badge beside PR number; page menu right of state badge, bold position · title · PR number; leading GitHub brand action; Reload right of filters, Updated line retained. Independent review found a P2 keyboard issue in the Reload move; failing real-production-session regression reproduced, chip iteration corrected, green afterward. Final focused61 Git/PR/design tests, earlier85 PR/stack/design tests and nine focused golden scenarios passed; full lint/types passed. Built-in browser confirmed sizes/color/weight, menu fit at750px actual CSS viewport, Reload tabIndex0/no aria-checked. Exact-head full gate, published CI and final installation remain required. Corresponding acceptance beads mb-am7d,mb-x1v5,mb-4kpu,mb-xvz2 stay open. Lower release-prep c67371c2 independently reviewed with no findings. Original28-layer stack is merged at68534af93; this new follow-up stack is not yet published. Experiment056 stopped on a valid444ms candidate first-row result exceeding350ms hard budget; preserve it, no complete paired verdict. Release remains unpublished pending further gates and owner approval.
