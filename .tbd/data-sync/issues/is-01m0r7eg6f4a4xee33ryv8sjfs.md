---
type: is
id: is-01m0r7eg6f4a4xee33ryv8sjfs
title: Implement the pluggable inventory engine
kind: feature
status: open
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-23-pluggable-inventory-engine.md
labels: []
dependencies: []
child_order_hints:
  - is-01m0r8ym1vvhwdmnx4xq48vk78
  - is-01m0r8xj4bv4bbrr65vw28d31j
  - is-01m0r8xt95921dabcddjjm7csf
  - is-01m0t5yhbk3cds1j6x33pvaf26
  - is-01m0t88jfkvafypd9h2sgvfz6p
  - is-01m0tb6n7zq5dvjf183rgwx1r1
  - is-01m0tbran58d9xzmdc6tx5vj2x
created_at: 2026-08-23T21:11:56.857Z
updated_at: 2026-08-24T17:05:42.052Z
---

## Notes

The semantic design and adoption gates remain in plan-2026-08-23-pluggable-inventory-engine.md. Delivery is now split by plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md into two independently shippable child features: mb-lsgg extracts the behavior-preserving Python reference provider with no fdu dependency; mb-hej8 depends on it and implements/evaluates the same contract through fdu. The atomic rollup/ETag bug mb-2cvn is a child of the Python phase. Planning work is tracked by mb-c7mk.
