---
type: is
id: is-01kyxybvqnw3fmmzhs3hnqhtxr
title: "P3: add bounded full-text search provider"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels: []
dependencies: []
parent_id: is-01kxnx9waq2h69ey9kb0mcg5hq
created_at: 2026-08-01T05:57:16.148Z
updated_at: 2026-08-16T08:05:43.312Z
extensions:
  linear:
    id: 02436c90-f79d-4b6e-84e1-f38d97b897e7
    linked_at: 2026-08-16T08:05:43.312Z
---
Spike and then implement an explicit bounded /api/search/text provider with path-and-location results, excerpts, cancellation, progress, scope, and honest truncation. Add the future persistent navigation-panel search surface and location-aware opening. Start with literal keywords; expose regex or approximate content matching only through provider capabilities after separate correctness, latency, and supply-chain evidence.
