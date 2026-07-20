---
type: is
id: is-01kxz30cg1b87r31kc0b9zd27c
title: "P2: SDK rollup surface and inventory-change event"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxz3131cqxh1xc4zdq4x9ss8
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:21:55.585Z
updated_at: 2026-07-20T06:22:32.007Z
---
plugin_sdk.js: fetchRollup(path, opts) with abort + defaults from METABROWSER_SETTINGS; watchRollup(path, opts, onUpdate) -> {refresh, dispose} listening for window CustomEvent metabrowser:inventory-change with ancestor-or-descendant path filter and trailing debounce (default 1000ms); ageBucket(mtimeSeconds) sharing formatAge thresholds (refactor app.js formatAge to call it); tooltip and fileTypeClass(path) proxies (pattern: icons proxy). app.js: notifyFileStoreSubscribers dispatches metabrowser:inventory-change with changed paths. Node vm tests for debounce/filter/dispose + registration. Scoped step toward mb-t1wt. See spec 'Plugin SDK'.
