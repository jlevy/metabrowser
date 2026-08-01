---
type: is
id: is-01kyxyb67v18br7jm7w8mrwss5
title: "Spike: slash-key fuzzy quick file navigation"
kind: epic
status: open
priority: 1
version: 11
spec_path: docs/project/specs/active/plan-2026-07-17-scalable-file-search.md
labels:
  - spike
dependencies:
  - type: blocks
    target: is-01kyxybpctnfvcbj8eh629hab0
parent_id: is-01kxnx9waq2h69ey9kb0mcg5hq
child_order_hints:
  - is-01kyxyyy0pj8hddy6584peh7yf
  - is-01kyxyza8j6h6hfcyqzvnhs9z2
  - is-01kyxyzjxyh94a9re1jps0mv23
  - is-01kyxyztmrk2yqjb8hz1trvt4e
  - is-01kyxz015gerf8zaryhqej89f8
  - is-01kyxz08ne4mbst6q9t742f808
  - is-01kyxz0fjsxaww2zkypg8wy78m
  - is-01kyxz0qkyygz3saxrxtzx3kqx
created_at: 2026-08-01T05:56:54.138Z
updated_at: 2026-08-01T06:08:40.061Z
---
Deliver the complete client-only Phase 1 spike: pressing slash opens a keyboard-first file finder, typing fuzzy-matches every filename observed by the browser, and accepting a result navigates to that file without a search request. The epic includes a documented and fixture-driven ranking algorithm, bounded and cancellable local search, accessible palette behavior, navigation and stale-result recovery, performance evidence, live-browser validation, and final spike findings. It intentionally excludes complete server filename search and file-content search.

## Notes

Mapped with the plan-implementation-with-beads shortcut on 2026-07-31. Children use TDD and strict browser modules. Ranking behavior is a reviewable contract: named score components, deterministic comparison order, rationalized golden scenarios, and before-and-after examples for future tuning.
