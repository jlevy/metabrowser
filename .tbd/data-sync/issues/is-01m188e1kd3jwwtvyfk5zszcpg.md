---
type: is
id: is-01m188e1kd3jwwtvyfk5zszcpg
title: test_views_models_routes enumerates fewer route modules than check_parity
kind: task
status: in_progress
priority: 3
version: 3
spec_path: docs/project/specs/done/plan-2026-08-21-cli-parity-and-golden-coverage.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-08-30T02:37:01.420Z
updated_at: 2026-11-01T17:59:49.966Z
started_at: 2026-11-01T16:05:47.680Z
---
tests/test_views_models_routes.py::test_browser_and_data_routes_match_the_route_table reads Route() registrations from server.py and git/routes.py only, so every route in events_route.py (/api/events, /api/catalog, /api/capabilities, /api/index/progress, /api/index/meta) was invisible to it. devtools/check_parity.py walks the whole package and now covers those, so the hole is mitigated rather than open. Tidy the older test to use the same enumeration, or narrow it explicitly to the modules it means to cover and say why, so two checks do not disagree about what counts as a registered route.

## Notes

2026-11-01: fixed in PR #274, open, CI green at its last read. Close when it merges; its required review has not run.
