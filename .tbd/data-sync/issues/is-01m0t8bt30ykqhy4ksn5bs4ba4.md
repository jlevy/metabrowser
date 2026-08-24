---
type: is
id: is-01m0t8bt30ykqhy4ksn5bs4ba4
title: Audit performance evidence and harness invariants from PR 73
kind: task
status: closed
priority: 1
version: 7
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - performance
  - validation
dependencies:
  - type: blocks
    target: is-01m0t8c0dr9dc0xkz1kvw6dya1
parent_id: is-01m0t88jfkvafypd9h2sgvfz6p
child_order_hints:
  - is-01m0t9zsx9vhh3bzp96mqkaa4z
created_at: 2026-08-24T16:06:26.143Z
updated_at: 2026-08-24T16:50:43.957Z
closed_at: 2026-08-24T16:50:43.956Z
close_reason: The landed performance evidence framework remains intact and now observes provider navigation/catalog paths directly; paired 100,000-file evidence and the complete verification gate pass.
resolution: null
duplicate_of: null
---
Trace every PR 73 profiler, evidence-validity, build provenance, responsiveness, readiness, semantic-equivalence, retained-heap, benchmark, and documentation invariant through the provider-axis changes. Ensure provider provenance extends rather than weakens the landed framework.

## Notes

Provider and contract identity extend rather than weaken the landed harnesses. All validity, visibility, responsiveness, attribution, retained-heap, build provenance, semantic-equivalence, and budget checks remain. Added provider-neutral navigation/catalog axes and fixed the synthetic corpus validity defect. The 319-test subset and full make verify pass. At 100,000 files, repeated navigation is 44.1 to 0.8 ms, retained catalog body 574.1 to 2.5 ms, catalog 304 577.9 to 1.0 ms, and settled visits 5.94M to 1.29M with identical catalog bytes and no semantic errors.
