---
type: is
id: is-01kxnxdnrcd3p2ghhgb50j5t3x
title: Add opt-in trusted-local file editing
kind: feature
status: open
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-07-16-trusted-local-file-editing.md
labels: []
dependencies: []
parent_id: is-01kxnx985gd2k5epmcswersqdk
created_at: 2026-07-16T16:51:09.708Z
updated_at: 2026-11-20T19:15:57.065Z
extensions: {}
---
Design and implement an explicitly enabled trusted-local file editing capability with confinement, optimistic concurrency, atomic writes, and plugin integration.

## Notes

2026-11-14 audit: the startup gate is on main (--allow-edits, METAB_ALLOW_EDITS, CAPABILITIES block; capabilities.py, PR #209). No write route consumes it. The regular-file rename and quarantine-trash slice is mb-0d6a (menu-primitives plan Phase 2).
