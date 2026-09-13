---
type: is
id: is-01m26s72hwqbm3076hxa0p5z4c
title: Restore exact-final 300k headed-browser performance gates
kind: bug
status: closed
priority: 0
version: 8
labels:
  - release-hardening
  - performance
dependencies: []
child_order_hints:
  - is-01m26wh00p5dkkg8m9dcnzmkq9
  - is-01m26ymgwv202bwqsyz7cg0q8v
  - is-01m27v4gtr2kfwzvkns4ezvpsj
created_at: 2026-09-10T23:07:31.771Z
updated_at: 2026-09-13T16:43:30.978Z
closed_at: 2026-09-13T16:43:30.976Z
close_reason: All children closed. exp-032 final series (863dcd9c vs exact v0.9.1 wheel, 300k corpus, 5 interleaved pairs, harness 21) passes every hard responsiveness gate with admissible, nonce-unique evidence. Residual noisy-machine observations moved to mb-afdb.
resolution: null
duplicate_of: null
---
Exact-final headed Chrome benchmark at 8ffe964b failed the candidate hard gate inventory_delivery_max_ms <= 50 in all three valid 300k-file runs (81-171 ms) and showed cold FCP median 632 ms versus 148 ms at v0.9.1. Diagnose the unbounded delivery batch and eager-startup regression, implement bounded work, rerun exact interleaved control/candidate evidence, and require every hard gate green before installation.

## Notes

Implemented atomic scheduler-driven catalog snapshots with folded same-generation deltas, reconnect-generation rotation, safe canonical UTF-16 ordered immutable projections, memo release, bounded subtree removal, and separately gated JSON parsing. Added an O(batch) proved ordered-tail fast path while replacements, non-tail mutations, and delete boundaries retain the bounded general merge. Production 300k browserless sessions cover 256 head insert/update, small and full subtree removal, 4096 staged put tail, event-entry tail, cancellation, COW, ownership, and one complete publication. Focused 42 pytest plus catalog Node/Biome checks pass. Headed diagnostics: pre-fix inventory 1863ms/21%, max34ms, parse34ms; tail-fast inventory 310ms/1%, max17ms, parse17ms. KPress prewarm was 6.5ms; a noisy core stylesheet run measured75.9ms against75 and remains rejected. Final immutable-wheel alternating n=3 comparison remains pending until concurrent Markdown/typography source changes settle.
