---
type: is
id: is-01kxz30c541p7r1sezr4dt4g78
title: "P2: /api/rollup route, wire models, settings"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels: []
dependencies:
  - type: blocks
    target: is-01kxz30cg1b87r31kc0b9zd27c
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-07-20T06:21:55.236Z
updated_at: 2026-07-20T07:30:25.387Z
closed_at: 2026-07-20T07:30:25.387Z
close_reason: "Implemented in the full spike (commits efccc10, e98f8a1, edea91c): folder envelope + rollup data plane + shell wiring + SDK surface + layout module + treemap renderer, all tested (745-test suite and make verify green)"
---
server.py: api_rollup handler mirroring api_tree guards; factor shared inventory start/cold-wait block into _ensure_inventory_serving(subpath) used by both; clamp depth/top/ext_top. settings.py: ROLLUP_DEFAULT_DEPTH=3 MAX_DEPTH=6 DEFAULT_TOP=40 MAX_TOP=200 DEFAULT_EXT_TOP=12 MAX_EXT_TOP=32, exposed via client_settings_dict. wire_models.py: RollupDirNode/RollupFileNode/RollupRest + validate_rollup_node (pattern: validate_tree_node). Tests: tests/test_rollup_route.py (clamps, traversal, cold start, envelope fields index_status/indexed_files/max_files/truncated), extend tests/test_browser_wire_shape.py. No ETag v1; gzip middleware covers bodies. See spec 'Server: Rollup Query and Route'.
