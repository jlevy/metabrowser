---
type: is
id: is-01m2gb3gpn7vcsw0as4xa243tg
title: Stabilize the test suite under machine load
kind: bug
status: open
priority: 2
version: 6
labels:
  - testing
dependencies: []
child_order_hints:
  - is-01m2gb3pfd368gdf1ragzqezbg
created_at: 2026-09-14T16:13:19.443Z
updated_at: 2026-11-14T18:42:10.880Z
---
Sweep the full pytest suite and tryscript goldens under heavy machine load (load average 7-50 from an unrelated workload, or CPU burners on a quiet host). Classify each failure as a load or timing flake, a real bug, or an order dependence, and fix flakes by asserting the product guarantee with deterministic coordination rather than wall-clock thresholds. The starting flake, tests/test_serve_open_race.py (mb-0mu9), is fixed. CI flakes found since are tracked as children of this bead.

## Notes

2026-09-20: status returned to open (was in_progress). The stated gate, "before v0.10.0",
has passed: v0.10.0 was tagged 2026-09-15 (git tag v0.10.0, commit dated 2026-09-15). The
sweep is not in flight, and the known flake it starts from is still tracked by the open
child mb-0mu9 (confirmed open on 2026-09-20).

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

The starting readiness flake mb-0mu9 is now closed; the 2026-09-20 statement that it remained open is historical. This does not prove the requested whole-suite heavy-load sweep or classify every timing/order-dependent failure. Keep this broader task open.
