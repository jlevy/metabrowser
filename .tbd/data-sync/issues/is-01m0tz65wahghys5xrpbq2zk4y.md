---
type: is
id: is-01m0tz65wahghys5xrpbq2zk4y
title: "Step 6: Finish split interaction, styling, and contrast"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-24-diff-syntax-highlighting-and-layouts.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0tz6g44qzh76psm0gg91ays
parent_id: is-01m0tz401dw1bceer6knws0s7a
created_at: 2026-08-24T22:45:18.856Z
updated_at: 2026-08-24T22:45:29.347Z
---
Files and functions: src/metabrowser/builtin_plugins/diff/styles.css selectors for diff-toolbar, diff-layout-control, diff-line-token-host, diff-split-row/sides/padding, selection gates, overflow, and reduced motion; src/metabrowser/builtin_plugins/diff/diff-view.js installSplitSelectionGate/dispose path; tests/dom/diff-view-behavior.js; tests/test_syntax_palette.py contrast composition helpers and diff tint cases. Behavior: keep token hosts transparent; size split code columns with a practical minimum and horizontal scrolling; keep hunk/fold rows full width; on pointer-down activate exactly one source side and suppress user-select on the other until pointer-up/cancel, while full-width controls clear the gate. Invariants: design tokens only, no plugin syntax palette, no background on token spans, numbers/markers/padding remain unselectable and non-accessible as source, radiogroup remains keyboard reachable, and all semantic syntax foregrounds meet 4.5:1 over context/add/delete surfaces in light and dark themes. Acceptance: DOM event tests cover side gate installation/release/disposal and headers; CSS contract checks cover transparent hosts, overflow, minimum widths, and reduced motion; palette tests pass every token/tint/theme combination.
