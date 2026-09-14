---
type: is
id: is-01m2fc50c88y8yb8gw1mtemabc
title: "PR #116 review R3: activity golden describes one test that is really two"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2fc4y836btjbcn5xa0skzp3
created_at: 2026-09-14T07:12:22.406Z
updated_at: 2026-09-14T07:29:20.394Z
closed_at: 2026-09-14T07:29:20.393Z
close_reason: "Fixed in 85fc77d1 (PR #116): cli-api-nav activity prose names both tests and what each asserts (reword option chosen; the pair already covers tracker, overlay, and route)."
resolution: null
duplicate_of: null
---
tests/golden/cli-api-nav.tryscript.md:449-450. test_tick_refreshes_facts_then_marks_the_overlay_active drives two ticks; test_api_activity_reads_the_same_overlay_snapshot reads active_files through the handler. Describe both accurately.
