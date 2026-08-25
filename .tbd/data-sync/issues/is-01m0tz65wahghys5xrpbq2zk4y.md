---
type: is
id: is-01m0tz65wahghys5xrpbq2zk4y
title: "Step 6: Finish split interaction, styling, and contrast"
kind: task
status: closed
priority: 2
version: 7
spec_path: docs/project/specs/done/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0tz6g44qzh76psm0gg91ays
parent_id: is-01m0tz401dw1bceer6knws0s7a
created_at: 2026-08-24T22:45:18.856Z
updated_at: 2026-08-25T00:07:07.612Z
closed_at: 2026-08-24T23:44:51.926Z
close_reason: Acceptance criteria pass; interaction, styling, and contrast contracts are covered.
resolution: null
duplicate_of: null
---
Files and functions: src/metabrowser/builtin_plugins/diff/styles.css selectors for diff-toolbar, diff-layout-control, diff-line-token-host, diff-split-row/sides/padding, selection gates, overflow, and reduced motion; src/metabrowser/builtin_plugins/diff/diff-view.js installSplitSelectionGate/dispose path; tests/dom/diff-view-behavior.js; tests/test_syntax_palette.py contrast composition helpers and diff tint cases. Behavior: keep token hosts transparent; size split code columns with a practical minimum and horizontal scrolling; keep hunk/fold rows full width; on pointer-down activate exactly one source side and suppress user-select on the other until pointer-up/cancel, while full-width controls clear the gate. Invariants: design tokens only, no plugin syntax palette, no background on token spans, numbers/markers/padding remain unselectable and non-accessible as source, radiogroup remains keyboard reachable, and all semantic syntax foregrounds meet 4.5:1 over context/add/delete surfaces in light and dark themes. Acceptance: DOM event tests cover side gate installation/release/disposal and headers; CSS contract checks cover transparent hosts, overflow, minimum widths, and reduced motion; palette tests pass every token/tint/theme combination.

## Notes

Implemented and validated split-side selection gating with full-width reset/disposal, explicit overflow/min-width geometry, transparent token hosts, reduced-motion coverage, and computed 4.5:1 light/dark contrast over context/add/delete tints. Focused tests: 7 passed; full make verify: 1514 pytest + 48 golden, lint/types/audits/distribution all green.
