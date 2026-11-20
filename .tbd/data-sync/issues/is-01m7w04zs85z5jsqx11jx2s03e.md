---
type: is
id: is-01m7w04zs85z5jsqx11jx2s03e
title: "Warm a dependent's declared providers in the browser (PR #649 A9)"
kind: feature
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7vtd09bppvgqam5h87zpnvh
hold: null
hold_until: null
created_at: 2026-11-20T08:11:15.624Z
updated_at: 2026-11-20T08:29:48.187Z
started_at: 2026-11-20T08:11:22.674Z
---
From PR #649 review A, A9 (Low, suggestion for layer 2): https://github.com/jlevy/metabrowser/pull/649#pullrequestreview-5989412950

The browser never learns a plugin's requires: server.py _build_plugin_asset_config_block's descriptor carries no requires, so a dependent that needs its provider on every render (a table source plugin needs table) waits for its own module before the provider's stylesheets, scripts and module are requested. Fix in Phase 2 (table protocol): add requires to each descriptor and have _startPluginAssets warm declared providers (stylesheets and modulepreload, no evaluation), or let a manifest mark a requirement as always needed; loadPluginExports could also call _startPluginAssets before awaiting the view helpers, as loadPluginsForKind does. Measure the startup-script budget (devtools/check_startup_scripts.py) since this adds eager SDK code. Waits on: Phase 2's first table source plugin, the consumer that needs it.

## Notes

Dispositioned deferred on PR #649 review A; lives under Phase 2 (mb-15f0) because its first consumer is layer 2.
