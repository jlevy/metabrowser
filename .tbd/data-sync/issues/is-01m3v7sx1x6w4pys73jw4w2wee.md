---
type: is
id: is-01m3v7sx1x6w4pys73jw4w2wee
title: "Tests: convert the three sleeps PR #252 left, and settle the item-reversed run"
kind: task
status: open
priority: 3
version: 7
spec_path: docs/project/specs/done/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
hold: null
hold_until: null
created_at: 2026-10-01T08:02:59.257Z
updated_at: 2026-11-14T18:49:58.570Z
started_at: 2026-11-01T16:21:31.357Z
---
The process-global resets this bead first asked for landed in PR #276 (commit 8e56775d, tests/conftest.py:272-286): probe results, the ignore cache and the catalog revision are reset, and the fixture says why tree_source._POOLS, dotenv._reported and server._EXTRA_ALLOWED_HOSTS are left alone. No failure was traced to that state.

Still open from PR #252 (mb-onzb): three real sleeps not converted to events or counts (tests/test_browser_v2.py:518 and :637, tests/test_cache_update.py:385), and a whole-suite item-reversed run, which was inconclusive under load. Show an order dependence before adding any further reset. Not labelled v0.12: CI passes in module-reversed order.

## Notes

2026-11-01: fixed in PR #276, open, CI green at its last read. Close when it merges; its required review has not run. Precautionary: the reset is in place, but no failure was traced to this state.

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

PR #276 and its required reviews are complete and merged, including the precautionary process-global resets. No causal order-dependent failure was established by that reset, and this landing note supplies neither a conclusive whole-suite item-reversed result nor completion of the remaining sleep/causality checks. Keep this qualified testing task open.
