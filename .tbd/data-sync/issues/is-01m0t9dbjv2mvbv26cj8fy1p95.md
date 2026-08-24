---
type: is
id: is-01m0t9dbjv2mvbv26cj8fy1p95
title: Restore constant-time catalog ETag and body-cache hits
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - inventory-provider
  - performance
dependencies: []
parent_id: is-01m0t8bsb54j16rhfdmwj5q0vh
created_at: 2026-08-24T16:24:45.402Z
updated_at: 2026-08-24T16:50:29.632Z
closed_at: 2026-08-24T16:50:29.631Z
close_reason: Added constant-work diagnostics preflight so retained bodies and 304s avoid CatalogQuery; the 100,000-file retained-body/304 p50 values fell from 574.1/577.9 ms to 2.5/1.0 ms and make verify passes.
resolution: null
duplicate_of: null
---
The provider migration calls _read_catalog before checking If-None-Match or the retained encoded-body cache, so every 304 and same-version reconnect still scans and sorts the full catalog. Add a constant-work diagnostics/version preflight, return matching validators or retained bodies before CatalogQuery, and revalidate against the coherent version returned by a cache-miss catalog read. Prove cache hits do not execute CatalogQuery.

## Notes

api_catalog now performs a DiagnosticsQuery checkpoint before any CatalogQuery. Matching If-None-Match and retained-body hits return without a catalog read. A test wraps coordinator.read and proves one initial CatalogQuery across an initial response, an unconditioned retained-body hit, and a conditional 304.
