---
type: is
id: is-01m6f3neny40jwz0qeanc3avfh
title: Re-run large-PR wall-clock claims on a quiet machine
kind: task
status: open
priority: 2
version: 4
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T21:46:51.453Z
updated_at: 2026-11-04T17:18:21.906Z
---
The study runs alongside other agents, so its wall-clock claims need a quiet re-run, with the rest of the release's quiet work in mb-cf6y.

## Notes

Include public cases with large files, since file count does not predict the page's cost and hydrated rows do (review of #284, E6): astral-sh/ruff #29817 (1,031 files, the study's own github.com case; 114,609 nodes before E1's fix) and astral-sh/ruff #29121 (1,627 files, +705,301 lines), beside the private 1,183-file case (44k nodes). Measure first line, longest task, Back and the Conversation click on each, in adjacent pairs against signed-out github.com.


2026-11-03: review E on PR 284 measured every figure under load (one-minute average 2.9 to 67), with adjacent pairs; the quiet re-run is still owed, after E1 lands.

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

The E1 fix and prepared-manifest improvement are now reviewed and merged, so the previous wait-for-E1 prerequisite is satisfied. The requested quiet-host adjacent public comparisons remain unrun by this reconciliation. Keep this task open, preserving the dated loaded-host measurements and their qualifications.
