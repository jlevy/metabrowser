---
type: is
id: is-01m0k4p20yey7mb3h4t9z4w94j
title: Move the Chart.js stack to the on-demand tier
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0k4p2s7ay3t761z9da84en0
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T21:47:26.621Z
updated_at: 2026-08-21T22:26:44.343Z
closed_at: 2026-08-21T22:26:44.342Z
close_reason: "Chart.js moved to the on-demand tier. static/asset_loader.js owns the loading, plugin_sdk.js publishes ensureAsset, the agent-log charts view awaits it. Measured on this repository, median of five cold loads of /view/README.md: load 853 ms -> 411 ms, transferred 823,391 B -> 732,836 B, vendored files on load 6 -> 3. Verified in Chromium that Chart is absent until ensureAsset resolves, that the annotation plugin and date adapter register in order, and that a repeat call and three concurrent calls cost nothing. Covered by tests/test_asset_loader_js.py and a tier assertion in tests/test_index_cdn_origins.py."
---
