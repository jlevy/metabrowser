---
type: is
id: is-01m188e1kd3jwwtvyfk5zszcpg
title: test_views_models_routes enumerates fewer route modules than check_parity
kind: task
status: closed
priority: 3
version: 4
spec_path: docs/project/specs/done/plan-2026-08-21-cli-parity-and-golden-coverage.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-08-30T02:37:01.420Z
updated_at: 2026-11-04T17:14:29.737Z
started_at: 2026-11-01T16:05:47.680Z
closed_at: 2026-11-04T17:14:29.737Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
tests/test_views_models_routes.py::test_browser_and_data_routes_match_the_route_table reads Route() registrations from server.py and git/routes.py only, so every route in events_route.py (/api/events, /api/catalog, /api/capabilities, /api/index/progress, /api/index/meta) was invisible to it. devtools/check_parity.py walks the whole package and now covers those, so the hole is mitigated rather than open. Tidy the older test to use the same enumeration, or narrow it explicitly to the modules it means to cover and say why, so two checks do not disagree about what counts as a registered route.

## Notes

2026-11-01: fixed in PR #274, open, CI green at its last read. Close when it merges; its required review has not run.
