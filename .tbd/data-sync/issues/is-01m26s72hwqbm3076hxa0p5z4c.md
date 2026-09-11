---
type: is
id: is-01m26s72hwqbm3076hxa0p5z4c
title: Restore exact-final 300k headed-browser performance gates
kind: bug
status: in_progress
priority: 0
version: 5
labels:
  - release-hardening
  - performance
dependencies: []
child_order_hints:
  - is-01m26wh00p5dkkg8m9dcnzmkq9
  - is-01m26ymgwv202bwqsyz7cg0q8v
created_at: 2026-09-10T23:07:31.771Z
updated_at: 2026-09-11T00:42:15.322Z
---
Exact-final headed Chrome benchmark at 8ffe964b failed the candidate hard gate inventory_delivery_max_ms <= 50 in all three valid 300k-file runs (81-171 ms) and showed cold FCP median 632 ms versus 148 ms at v0.9.1. Diagnose the unbounded delivery batch and eager-startup regression, implement bounded work, rerun exact interleaved control/candidate evidence, and require every hard gate green before installation.

## Notes

Implemented scheduler-driven atomic catalog transactions with one complete publication; folded same-generation catalog/fs deltas; rotated reconnect generations; canonical UTF-16 ordered safe snapshots; direct 256-entry fast path plus staged large subtree removal; memo release; separate response body/JSON parse instrumentation. Production JS/300k session, focused pytest, Biome, and strict TypeScript are green. KPress serve-only asset prewarm and eager-tier cuts are integrated in shared tree. Final wheel and interleaved headed n=3 comparison remain pending until concurrent Markdown/lazy fixes settle.
