---
type: is
id: is-01m7wbe5rqnhsgj5d2d46razrk
title: "test_golden_pin_age_groups failed once on CI (Python 3.12): all 7 files in older, as if the patched clock was not in effect"
kind: bug
status: open
priority: 1
version: 7
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-20T11:28:30.998Z
updated_at: 2026-11-20T17:34:00.388Z
---

## Notes

Seen again 2026-11-20 on CI Python 3.13 (unit 3.13, 2/2), run 44771587418 for jlevy/metabrowser PR 645 at 928e94edf merged with main: same signature, [('older', 7)] instead of [('24h', 1), ('older', 6)]. Other interpreters passed; the failed job was rerun.

Seen a third time 2026-11-20 on CI Python 3.14t (unit 3.14t, 1/2), run 44777918273 job 136432582834, for jlevy/metabrowser PR 602 at 1a2e3258b (a Swift-only change merged with main ab64b5c86, whose own run was green): same signature, ages {'state': 'ready', 'files': 7, 'dated': 7, 'older_than': None}, groups [('older', 'Older')]. The 24h group is absent, so new.py's stamp fell before as_of minus 24h: either as_of was not the patched content_routes._request_instant or new.py's stamp was not AGES_TIP. Three interpreters, so not specific to free-threading. Leads not yet checked: the process-wide file_ages_service and source.derived caches shared with earlier tests in the same xdist worker (the fast-import repo has identical oids in every test), and _GitTimes memo keys built from id(index).

2026-11-20 audit: mb-3m45 (filed the same day, main run 44779757308 and PR 662 run 44781044946; tests/test_cli_git_pin_golden.py:716 with content_routes._request_instant monkeypatched to AGES_TIP + 3 h) records the same failure; close whichever is not kept.


The parent of this bead is:
---
type: is
id: is-01m2gb3gpn7vcsw0as4xa243tg
title: Stabilize the test suite under machine load
kind: epic
status: open
priority: P2
version: 27
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
  - is-01m7wztr8mpkr8braes7adb6js
created_at: 2026-09-14T16:13:19.443Z
updated_at: 2026-11-20T17:30:36.334Z
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



Root cause (2026-11-20), PR 664 (claude/age-groups-golden-flake): tests/test_serve_pin.py::test_a_served_pin_has_its_routes_before_its_first_request deleted metabrowser.git.content_routes from sys.modules so a pin's serve would import it again; undoing the deletion restored the old module in sys.modules but left the re-imported one as the package's attribute metabrowser.git.content_routes. Afterwards `from metabrowser.git import content_routes` (what the golden patches _request_instant on) read the new module while the server's per-request `from metabrowser.git.content_routes import git_revision_tree_groups` read the old one, so the fixed clock never reached the routes and every 2020 file was older. It depends on which tests an xdist worker ran before it, hence one interpreter or another, and a rerun passing. Reproduced on main in one process: test_golden_pin_file_ages, then the serve test, then test_golden_pin_age_groups. Fix: tests/forgotten_module.py forget_module restores both, an invariant test (fails with the old technique), and an autouse guard in conftest naming any test that leaves a metabrowser module as two objects. test_git_revision_ages_routes.py patched the clock the same way and was exposed too.
