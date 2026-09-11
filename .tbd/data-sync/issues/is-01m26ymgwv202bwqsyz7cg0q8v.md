---
type: is
id: is-01m26ymgwv202bwqsyz7cg0q8v
title: Bound Markdown reconciliation across UI and graph analysis
kind: bug
status: in_progress
priority: 0
version: 2
labels:
  - release-hardening
  - performance
dependencies: []
parent_id: is-01m26s72hwqbm3076hxa0p5z4c
created_at: 2026-09-11T00:42:15.322Z
updated_at: 2026-09-11T00:42:19.126Z
---
Release review found that wiki fallback resolution scans the complete client catalog once per rendered target, nested transclusions own independent per-frame budgets, published-route adaptation repeats catalog probes synchronously, and route/CLI-visible Markdown graph analysis repeats the same target-by-catalog work. Implement one root-scoped, disposal-safe reconciliation coordinator with a lazy immutable-revision note index shared by nested content; budget preparation, lookup, and DOM commits; reuse snapshot-scoped published-route context; preserve exact candidateCount with bounded preview semantics across UI and graph outputs; and pin exact browserless/golden parity plus headed memory/tick evidence.
