---
type: is
id: is-01m0tybh589avf526rvh35kzqj
title: Version or preserve the released plugin asset lifecycle
kind: bug
status: open
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0vcqjmdqs2zhk804rgbjjm9
  - type: blocks
    target: is-01m0vdm7d6j696m0acyqxsq215
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-24T22:30:45.671Z
updated_at: 2026-08-25T02:57:39.237Z
---
Release-readiness finding on main c123ae6. Version 0.6.0 eagerly loaded every plugin stylesheet, classic script, and index module with the page; v0.7 intentionally loads them only after a selected kind. Treat that lifecycle change as a plugin contract break: add a failing SDK-gate test first, bump PLUGIN_SDK_VERSION to 0.5, update every built-in manifest, document when extra_styles, extra_scripts, and index.js load, and describe the aggregate v0.7 behavior without an intermediate-fix entry. Preserve the existing startup asset budgets (at most 25 requests and 175 KB).
