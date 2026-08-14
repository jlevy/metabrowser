---
type: is
id: is-01kzz5nacf7yqmqywq92t4d7tv
title: Accept signed registry order and priority in browser adapter
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - file-types
  - review
dependencies: []
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T03:39:42.350Z
updated_at: 2026-08-14T03:39:47.070Z
closed_at: 2026-08-14T03:39:47.069Z
close_reason: Browser integer validation now accepts signed values, retains positive checks for revision and the fixed component cap, and has a VM regression covering negative order and priority.
---
Align the browser Registry v1 validator with the Python loader and JSON Schema, where group/family order and kind priority are signed integers. Add a browser conformance regression.
