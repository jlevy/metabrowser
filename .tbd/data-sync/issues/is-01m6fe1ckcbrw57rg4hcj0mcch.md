---
type: is
id: is-01m6fe1ckcbrw57rg4hcj0mcch
title: "Decide the size of a diff's code: 13.6px from a token nothing defines, or the ramp's 12px"
kind: task
status: in_progress
priority: 3
version: 3
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3nkg482640stjteqx3fvw
hold: null
hold_until: null
created_at: 2026-11-03T00:48:08.299Z
updated_at: 2026-11-04T02:28:29.861Z
started_at: 2026-11-04T02:28:29.861Z
---
--code-font-size is defined nowhere, so .diff-line and .diff-split-side read at their fallback 0.85rem, 13.6px, and follow the browser's root size. The ramp's --mono-block-font-size is 12px. Moving to it shrinks every diff on every page, which is the owner's decision. tests/test_design_vocabulary.py holds the exemption until then. From review A finding A8 on PR #280.

## Notes

2026-11-03 owner follow-up under new design-system scope mb-yb9q: the owner now asks for dense type-scale consistency after observing oversized mono in PR Files changed. Read-only audit confirms the inherited undefined --code-font-size fallback0.85rem at unified/split rows, repeated by reserveBody; root16px gives13.6px versus shared dense mono12px, and browser-root changes affect only the diff. Existing history/parent retained. Proposed minimal correction is the three runtime sites plus removal of two explicit vocabulary exemptions; preserve KPress15px-based graded prose code and font-family modes, no global shrink/new font. Primary source history and proposal preserved as typography-audit-224e32aa/AUDIT.json,AUDIT.md,PROPOSED.patch. Actual IAB computed styles owned by coordinator; source remains frozen while224gate runs. No implementation applied.
