---
type: is
id: is-01m0r7eg6f4a4xee33ryv8sjfs
title: Implement the pluggable inventory engine
kind: feature
status: open
priority: 1
version: 22
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
  - is-01m1mv9zmvtf5nnr5kjs16vq6k
  - is-01m0gzsgfwnvg4nqf3krady4tt
  - is-01m1mva0nyrz9m77r1ab7jexhc
  - is-01m1d3qcqc15jmht1zm496mjqb
  - is-01m1mva0attgkp1h6b4h0d8ymd
  - is-01m1mv9zzrzt294qxymy3bnhfh
  - is-01m1d3qscgv75446y3x56tyhbj
  - is-01kzcwmhbancvf58sxae7c6qpf
  - is-01m1mva118h2a2j3b8swefvk8y
created_at: 2026-08-23T21:11:56.857Z
updated_at: 2026-11-14T18:48:20.531Z
---
Parent for the pluggable inventory engine (docs/project/specs/active/plan-2026-08-23-pluggable-inventory-engine.md; implementation plan in plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md). Phase 1, the Python reference provider behind the sealed provider contract, shipped in v0.10.0 through #74, #99, and #101 (mb-lsgg, closed). Phase 2, the fdu provider and its adoption gates, is mb-hej8.

## Notes

The semantic design and adoption gates remain in plan-2026-08-23-pluggable-inventory-engine.md. Delivery is now split by plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md into two independently shippable child features: mb-lsgg extracts the behavior-preserving Python reference provider with no fdu dependency; mb-hej8 depends on it and implements/evaluates the same contract through fdu. The atomic rollup/ETag bug mb-2cvn is a child of the Python phase. Planning work is tracked by mb-c7mk.
