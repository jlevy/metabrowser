---
type: is
id: is-01m2fc512q8p272mvcak2w67hz
title: "PR #116 review S1: build the round-trip payload from CURSOR_PATHS and ELAPSED_PATHS"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2fc4y836btjbcn5xa0skzp3
created_at: 2026-09-14T07:12:23.125Z
updated_at: 2026-09-14T07:29:20.917Z
closed_at: 2026-09-14T07:29:20.915Z
close_reason: "Applied in 85fc77d1 (PR #116): round-trip test payload built from CURSOR_PATHS and ELAPSED_PATHS, asserting placeholders at each address."
resolution: null
duplicate_of: null
---
tests/test_normalize.py:63. The 'every unstable field' test omits cursor, previous_cursor, and inventory.duration_ms; derive the payload from the path tuples.
