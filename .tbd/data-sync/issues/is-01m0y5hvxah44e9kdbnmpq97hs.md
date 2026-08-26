---
type: is
id: is-01m0y5hvxah44e9kdbnmpq97hs
title: "Phase 4.8.3: Validate diff visual hierarchy in a real browser and reconcile release docs"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0y5hw7w8fdw9herhmph9qqs
parent_id: is-01m0y5h1kk1waq5baqsvmqcx6k
created_at: 2026-08-26T04:34:16.617Z
updated_at: 2026-08-26T04:38:25.824Z
---
Files/functions:
- Exercise the existing diff browser fixture and/or exact installed build with representative refined, unrelated, addition-only, and deletion-only rows in unified and split layouts.
- Inspect light and dark themes, line-number alignment, selection, syntax foregrounds, and console output.
- Update CHANGELOG.md plus the Phase 4.8 implementation outcome and research evidence with the final token mix and observed results.

Behavior/invariants:
- Changed spans read stronger than unchanged portions without hiding syntax.
- Gutter bars are visible and aligned for every changed line on both sides/layouts.
- No white flash, layout shift, added DOM, exception, or measurable scripting path is introduced.

Acceptance:
- Capture reproducible browser evidence or screenshots when useful.
- make format and focused browser scenarios pass.
