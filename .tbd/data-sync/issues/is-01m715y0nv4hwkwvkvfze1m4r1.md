---
type: is
id: is-01m715y0nv4hwkwvkvfze1m4r1
title: Coalesce identical GitHub CLI reads without blocking distinct requests
kind: feature
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m715sezspp55zz5v346nrv9n
created_at: 2026-11-09T22:12:48.953Z
updated_at: 2026-11-09T22:12:48.953Z
---
Add per-key single-flight for validated REST and read-only GraphQL requests. Scope by effective authorization, host, request variant, query/cursor, ETag, and response limits. Different keys run concurrently under the provider budget. Cancellation detaches a waiter; failures clear the flight safely. Reuse resource-specific locks and generation checks for durable publication across processes. Test distinct accounts, conditional responses, timeout, cancellation and out-of-order updates.
