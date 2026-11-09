---
type: is
id: is-01m715y0nv4hwkwvkvfze1m4r1
title: Coalesce identical GitHub CLI reads without blocking distinct requests
kind: feature
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m715sezspp55zz5v346nrv9n
created_at: 2026-11-09T22:12:48.953Z
updated_at: 2026-11-09T23:32:17.803Z
---
Add per-key single-flight for validated REST and read-only GraphQL requests. Scope by effective authorization, host, request variant, query/cursor, ETag, and response limits. Different keys run concurrently under the provider budget. Cancellation detaches a waiter; failures clear the flight safely. Reuse resource-specific locks and generation checks for durable publication across processes. Test distinct accounts, conditional responses, timeout, cancellation and out-of-order updates.

## Notes

Reviewed PR #346 design at 63d5d7fab9fd1dadb2c1481c7ad24d4ded37ea0a (https://github.com/jlevy/metabrowser/pull/346) keeps exact REST and read-only GraphQL request identity, conditional headers and auth provenance, distinct-key concurrency, cancellation teardown, and independent auth verification. Measure overlap first. Implementation remains planned.
