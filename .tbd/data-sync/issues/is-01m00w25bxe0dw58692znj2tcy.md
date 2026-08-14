---
type: is
id: is-01m00w25bxe0dw58692znj2tcy
title: Standardize rollup chooser as Files then Bytes
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - overview
  - treemap
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-14T19:30:26.300Z
updated_at: 2026-08-14T19:37:59.951Z
closed_at: 2026-08-14T19:37:59.950Z
close_reason: Implemented Files-first metric ordering and Files default while preserving saved choices; validated both views and CI.
---
Render the shared folder rollup metric chooser in Files then Bytes order in every host, default to Files when no saved preference exists, retain explicit saved choices, and update behavioral tests and design-system documentation. Validate Overview and Treemap use the same stateful control.
