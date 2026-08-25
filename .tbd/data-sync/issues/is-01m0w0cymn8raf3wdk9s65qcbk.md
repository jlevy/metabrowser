---
type: is
id: is-01m0w0cymn8raf3wdk9s65qcbk
title: "PR #74 scope audit S3: disambiguate provider and HTTP progress models"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T08:25:43.829Z
updated_at: 2026-08-25T08:25:43.829Z
---
events_route.IndexProgress is an HTTP response envelope while inventory_engine.contract.IndexProgress is provider progress. Rename the route-local model to IndexProgressEnvelope so reviews and type traces cannot confuse the two boundaries.
