---
type: is
id: is-01m0t9dbjv2mvbv26cj8fy1p95
title: Restore constant-time catalog ETag and body-cache hits
kind: bug
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - performance
dependencies: []
parent_id: is-01m0t8bsb54j16rhfdmwj5q0vh
created_at: 2026-08-24T16:24:45.402Z
updated_at: 2026-08-24T16:24:45.402Z
---
The provider migration calls _read_catalog before checking If-None-Match or the retained encoded-body cache, so every 304 and same-version reconnect still scans and sorts the full catalog. Add a constant-work diagnostics/version preflight, return matching validators or retained bodies before CatalogQuery, and revalidate against the coherent version returned by a cache-miss catalog read. Prove cache hits do not execute CatalogQuery.
