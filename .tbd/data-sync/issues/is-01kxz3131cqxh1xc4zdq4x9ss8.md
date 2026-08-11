---
type: is
id: is-01kxz3131cqxh1xc4zdq4x9ss8
title: "P3: treemap renderer with toggles, colors, interactions"
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxz313d3ghvd3r2jbgdh0qkb
  - type: blocks
    target: is-01kxz313qt7zrvvc4rymbjxnhs
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:22:18.668Z
updated_at: 2026-07-20T07:30:25.398Z
closed_at: 2026-07-20T07:30:25.398Z
close_reason: "Implemented in the full spike (commits efccc10, e98f8a1, edea91c): folder envelope + rollup data plane + shell wiring + SDK surface + layout module + treemap renderer, all tested (745-test suite and make verify green)"
---
builtin_plugins/folder/index.js treemap view: toolbar with three joined toggle groups (metric bytes|files, grouping folder|type, color age|type) + three-state gitignored control (shown|dimmed default|hidden); state persisted under localStorage key metabrowser.folder.treemap; layout via MetabrowserTreemapLayout; toggle changes relayout without refetch (dual aggregates + dominant_ext already in payload). Colors: age via mb.ageBucket -> new --file-age-fill-* tokens (add with dark overrides in core styles.css); type via ft-* class (files) and dominant_ext (dirs); dimmed = muted opacity class; hidden = relayout on unignored aggregates. Interactions: dir cell mb.openPath (zoom=navigation), file cell opens file, hover mb.tooltip (path/size/count/age), roving tabindex + arrows + Enter + Backspace-to-parent, accessible names, pending skeleton cells, truncated-index notice. Plugin styles.css tokens-only. DOM tests for toggles/zoom/keyboard.
