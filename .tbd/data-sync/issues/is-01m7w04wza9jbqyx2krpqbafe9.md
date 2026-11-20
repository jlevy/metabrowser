---
type: is
id: is-01m7w04wza9jbqyx2krpqbafe9
title: "PR #649 A3: startup budget met by deleting SDK types and checks"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7w04vfg21q09dmkkdsmbzwp
hold: null
hold_until: null
created_at: 2026-11-20T08:11:12.746Z
updated_at: 2026-11-20T08:47:32.680Z
started_at: 2026-11-20T08:11:20.564Z
closed_at: 2026-11-20T08:47:32.680Z
close_reason: "fixed in eb2db7d5c: metabrowser.chart moved to charts.js in the chart bundle (665 compressed bytes), plugin table types and configureAssets kind check restored; shell 599 bytes under at that commit (419 at head), recorded in performance-budgets.toml; CI run 44703997703 green at 70f180380153ea5a6531e32e219e4ddf2d427883"
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/static/plugin-sdk.js:170-172, 313-316, 381; devtools/check_startup_scripts.py; performance-budgets.toml. Review: https://github.com/jlevy/metabrowser/pull/649#pullrequestreview-5989412950
