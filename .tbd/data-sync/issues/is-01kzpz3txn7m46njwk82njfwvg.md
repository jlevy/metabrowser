---
type: is
id: is-01kzpz3txn7m46njwk82njfwvg
title: Optionally mirror extension and size filters upstream
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels:
  - ui
  - backend
dependencies: []
parent_id: is-01kzp82ktssqmf4fhm8sxmvb6p
created_at: 2026-08-10T23:11:22.545Z
updated_at: 2026-08-10T23:11:22.545Z
---
Type and size are decided client-side over rendered rows, so their answer is bounded by what has been expanded. For a very large directory that becomes incomplete rather than merely slow, which is the threshold worth moving on (see docs/architecture.md, 'Where Filtering Happens'). Extension and size are cheap index predicates and compose with the existing recency scan; activity is not a candidate, since the live set is small, client-held and already complete. Costs: a round trip per change on controls that feel instant today, cache keys multiplied by filter combination, and a dimension evaluated in two places that can disagree. FilterState already holds the vocabulary and the shared predicates, so a dimension can move tiers without changing meaning. Blocked on the planned server-side traversal work.
