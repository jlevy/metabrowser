---
type: is
id: is-01m2gb3gpn7vcsw0as4xa243tg
title: Stabilize the test suite under machine load
kind: epic
status: open
priority: 2
version: 26
labels:
  - testing
dependencies: []
child_order_hints:
  - is-01m2gb3pfd368gdf1ragzqezbg
  - is-01m78t1gnwvycrdyscb1zz7tt0
  - is-01m79263has7e8xgs52tw6k12v
  - is-01m7kpndww8wehzg3zya4x6wy5
  - is-01m7kpnebx9r14tv5m3e3wrfwj
  - is-01m7mc3my1hb6ax05y8wxkyg82
  - is-01m7kaq8nw86eh3g3rkfr327ht
  - is-01m7rm5wmnmdjwe20g9crhn7xq
  - is-01m7w7pradjq6tw8rrdk7nmjw8
  - is-01m7wweb3xhf6783751gszs00g
  - is-01m7r85aq8z1h2bmyp7j29kyaq
  - is-01m7rhv61js9th33xvb82q4ahh
  - is-01m76zwwf5h3av6b0ykk5qsvyd
  - is-01m7wbe5rqnhsgj5d2d46razrk
  - is-01m7qyd1pqw0w2m51k7bzqjc4h
  - is-01m7pppk3pybq3yzgz64ttbx2a
  - is-01m7w1w8da04pw131z5jaxdqdr
  - is-01m7w7pt8rqjk0fk7jne3eh8db
  - is-01m7sbwjvm0smmadqp4w4ch1qr
created_at: 2026-09-14T16:13:19.443Z
updated_at: 2026-11-20T17:21:11.156Z
---
Sweep the full pytest suite and tryscript goldens under heavy machine load (load average 7-50 from an unrelated workload, or CPU burners on a quiet host). Classify each failure as a load or timing flake, a real bug, or an order dependence, and fix flakes by asserting the product guarantee with deterministic coordination rather than wall-clock thresholds. The starting flake, tests/test_serve_open_race.py (mb-0mu9), is fixed. CI flakes found since are tracked as children of this bead.

## Notes

2026-09-20: status returned to open (was in_progress). The stated gate, "before v0.10.0",
has passed: v0.10.0 was tagged 2026-09-15 (git tag v0.10.0, commit dated 2026-09-15). The
sweep is not in flight, and the known flake it starts from is still tracked by the open
child mb-0mu9 (confirmed open on 2026-09-20).

2026-11-04 final landing update: all 23 PRs in this delivery (21 feature PRs plus #297 and #298) are merged on main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9. Postlanding Review E: https://github.com/jlevy/metabrowser/pull/298#pullrequestreview-5772391263. Final-main CI passed all nine jobs: https://github.com/jlevy/metabrowser/actions/runs/41868009781. The verified global CLI is 0.11.1.dev1154+db52ec09; final installed-wheel, browser, coordinator manual and production-cache acceptance are complete. Current feature landing is fully accepted. Earlier pending-gate or no-merge statements are historical; preserve each original build, test and measurement provenance. This does not claim a v0.12.0 release, a quiet-host performance result or completion of separate future work.

The starting readiness flake mb-0mu9 is now closed; the 2026-09-20 statement that it remained open is historical. This does not prove the requested whole-suite heavy-load sweep or classify every timing/order-dependent failure. Keep this broader task open.

2026-11-20 audit: Converted from a bug to an epic on 2026-11-20 to hold the test flakes: Chrome tier, macOS tests, wall-clock assertions and the Git 2.56.1 test failure. Fast CI's flake beads (mb-v719, mb-6nn3, mb-644p) moved here from mb-h8zb.
