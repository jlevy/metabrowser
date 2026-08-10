---
type: is
id: is-01kzmnyznydb254wv11evz3r79
title: Segment-trie catalog index for subtree removal (deferred)
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies: []
created_at: 2026-08-10T01:52:57.533Z
updated_at: 2026-08-10T01:52:57.533Z
---
Deferred alternative to the batching fix in mb-r8yg. Replace the flat path map with nested maps keyed by path segment so a directory removal costs O(subtree) instead of O(catalog).

Only worth building past the design center, and gated on the payload/latency measurement checkbox in the Phase 2 plan. Below roughly 100k non-gitignored files the batched removal is enough; above it the dominant cost is the provider scan itself (about 0.8s measured at 50k candidates), so the real answer is the bounded server search in mb-3arq rather than client-side data-structure work.

Do NOT take the deferred-sweep route instead: marking removed prefixes and filtering at snapshot time needs a per-entry sequence number to keep remove-then-upsert ordering correct, which smuggles epoch semantics in through a performance patch. See the Phase 2.1 section of the plan for the full reasoning.
