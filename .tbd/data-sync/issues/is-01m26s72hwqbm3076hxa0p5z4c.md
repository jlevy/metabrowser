---
type: is
id: is-01m26s72hwqbm3076hxa0p5z4c
title: Restore exact-final 300k headed-browser performance gates
kind: bug
status: in_progress
priority: 0
version: 3
labels:
  - release-hardening
  - performance
dependencies: []
child_order_hints:
  - is-01m26wh00p5dkkg8m9dcnzmkq9
created_at: 2026-09-10T23:07:31.771Z
updated_at: 2026-09-11T00:05:22.579Z
---
Exact-final headed Chrome benchmark at 8ffe964b failed the candidate hard gate inventory_delivery_max_ms <= 50 in all three valid 300k-file runs (81-171 ms) and showed cold FCP median 632 ms versus 148 ms at v0.9.1. Diagnose the unbounded delivery batch and eager-startup regression, implement bounded work, rerun exact interleaved control/candidate evidence, and require every hard gate green before installation.
