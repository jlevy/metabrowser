---
type: is
id: is-01m715y0nv4hwkwvkvfze1m4r1
title: Coalesce identical GitHub CLI reads without blocking distinct requests
kind: feature
status: closed
priority: 2
version: 8
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7327d4wd92r1n5bnmr1b0zb
hold: null
hold_until: null
created_at: 2026-11-09T22:12:48.953Z
updated_at: 2026-11-11T16:41:46.043Z
started_at: 2026-11-10T15:46:31.773Z
closed_at: 2026-11-11T16:41:46.042Z
close_reason: "Landed on main in ab346bf8 via native stack #350 merge (2026-11-11): PR #348 measured overlapping gh reads (3 of 1,523 launches in server-flow tests) and removed the in-flight wrapper per review A5; each read runs on its own with a structural read-only GraphQL guard."
resolution: null
duplicate_of: null
---
Add per-key single-flight for validated REST and read-only GraphQL requests. Scope by effective authorization, host, request variant, query/cursor, ETag, and response limits. Different keys run concurrently under the provider budget. Cancellation detaches a waiter; failures clear the flight safely. Reuse resource-specific locks and generation checks for durable publication across processes. Test distinct accounts, conditional responses, timeout, cancellation and out-of-order updates.

## Notes

Reviewed PR #346 design at 63d5d7fab9fd1dadb2c1481c7ad24d4ded37ea0a (https://github.com/jlevy/metabrowser/pull/346) keeps exact REST and read-only GraphQL request identity, conditional headers and auth provenance, distinct-key concurrency, cancellation teardown, and independent auth verification. Measure overlap first. Implementation remains planned.

Validated REST and read-only GraphQL coalesce when explicit inherited environment credentials prove launch equivalence. Stored CLI accounts bypass sharing. Transport-level overlap dropped two commands to one, with 24 selected transport tests passing. Existing outer job-level limits are preserved.

Draft implementation: https://github.com/jlevy/metabrowser/pull/348 at 53bb1ac97. An overlap fixture reduced two equivalent explicit-credential gh calls to one subprocess.

#348 at e147395f5 passed all nine GitHub CI checks.
