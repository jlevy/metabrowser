---
type: is
id: is-01m0w40rak3wfpqh9cywg1sxcm
title: S17 Remove unsupported special-object contract kind
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - pr74-review
dependencies: []
parent_id: is-01m0w0bedsm82j3dxvv3148s7c
created_at: 2026-08-25T09:28:58.450Z
updated_at: 2026-08-25T09:28:58.450Z
---
The provider contract advertises EntryType.OTHER, but the Python walker classifies every non-directory/non-symlink object as a regular file, _internal_entry rejects OTHER, and events_route cannot serialize it. This is an unsupported speculative axis in a functionality-preserving refactor. Remove OTHER from the Phase 1 contract and narrow maintained docs/tests to the three representable kinds; keep any future special-object wire extension as separately measured work.
