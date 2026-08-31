---
type: is
id: is-01m1apdvky7cr2rfb4ey3xwved
title: "PR #89 F4: The map names a nonexistent adapter port"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m1apd8ye0cvejxessb3ppzjy
created_at: 2026-08-31T01:20:04.221Z
updated_at: 2026-08-31T01:40:12.551Z
closed_at: 2026-08-31T01:40:12.551Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #89."
resolution: null
duplicate_of: null
---
plan-2026-08-28-cli-first-delivery-map.md sketches WorkingTreeAdapter(ComparisonAdapter) with describe/file_patch. The real port is DiffSource with four different methods in diff/adapters/base.py:21-30.
