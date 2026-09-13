---
type: is
id: is-01m26ymgwv202bwqsyz7cg0q8v
title: Bound Markdown reconciliation across UI and graph analysis
kind: bug
status: closed
priority: 0
version: 3
labels:
  - release-hardening
  - performance
dependencies: []
parent_id: is-01m26s72hwqbm3076hxa0p5z4c
created_at: 2026-09-11T00:42:15.322Z
updated_at: 2026-09-11T08:26:21.078Z
closed_at: 2026-09-11T08:26:21.077Z
close_reason: Replaced unbounded duplicate Markdown scans with a root-shared, disposal-safe worker and reconciliation coordinator, removed the unconsumed second graph grammar, bounded parser and DOM work including 2M adversarial and 8MiB degradation cases, restored TOC scrollspy, and added exact browserless/golden parity. Full 2044-test and 122-golden gates pass.
resolution: null
duplicate_of: null
---
Release review found that wiki fallback resolution scans the complete client catalog once per rendered target, nested transclusions own independent per-frame budgets, published-route adaptation repeats catalog probes synchronously, and route/CLI-visible Markdown graph analysis repeats the same target-by-catalog work. Implement one root-scoped, disposal-safe reconciliation coordinator with a lazy immutable-revision note index shared by nested content; budget preparation, lookup, and DOM commits; reuse snapshot-scoped published-route context; preserve exact candidateCount with bounded preview semantics across UI and graph outputs; and pin exact browserless/golden parity plus headed memory/tick evidence.
