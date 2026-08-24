---
type: is
id: is-01m0t8c0dr9dc0xkz1kvw6dya1
title: Run the upstream performance compatibility matrix
kind: task
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - performance
  - validation
dependencies: []
parent_id: is-01m0t88jfkvafypd9h2sgvfz6p
created_at: 2026-08-24T16:06:32.631Z
updated_at: 2026-08-24T16:59:34.132Z
closed_at: 2026-08-24T16:50:54.474Z
close_reason: The full upstream compatibility matrix, semantic A/B benchmark, and mandatory repository verification gate all pass against the current origin/main tip.
resolution: null
duplicate_of: null
---
Run focused structural, backend, browser, benchmark, and performance-loop tests plus representative serving measurements after every upstream invariant has a disposition. Compare semantic outputs and performance shape, then run make verify and leave PR 74 green and mergeable.

## Notes

Compatibility matrix complete against origin/main bae51fd (PR 73). The branch changes 20 of PR 73's 257 touched files; the other 237 remain byte-identical by ancestry. Every backend, browser, and harness invariant has a disposition. The 319-test focused matrix passed, followed by the final make verify: 1,556 tests passed and 1 skipped, 48 CLI goldens passed, both dependency audits were clean, and distribution/plugin/API checks passed. Paired 100,000-file serving runs produced identical 5,065,580-byte catalogs and no semantic errors while repeated navigation/catalog work fell sharply. The final interface audit also replaced a dummy diagnostics preflight with the zero-projection checkpoint required by the shared provider contract.
