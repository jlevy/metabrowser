---
type: is
id: is-01m6fe1ckcbrw57rg4hcj0mcch
title: "Decide the size of a diff's code: 13.6px from a token nothing defines, or the ramp's 12px"
kind: task
status: in_progress
priority: 3
version: 4
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3nkg482640stjteqx3fvw
hold: null
hold_until: null
created_at: 2026-11-03T00:48:08.299Z
updated_at: 2026-11-04T02:56:03.152Z
started_at: 2026-11-04T02:28:29.861Z
---
--code-font-size is defined nowhere, so .diff-line and .diff-split-side read at their fallback 0.85rem, 13.6px, and follow the browser's root size. The ramp's --mono-block-font-size is 12px. Moving to it shrinks every diff on every page, which is the owner's decision. tests/test_design_vocabulary.py holds the exemption until then. From review A finding A8 on PR #280.

## Notes

Owner-authorized fifth layer replaces the undefined code-font-size fallback at both diff row selectors and reserveBody with mono-block-font-size. Removed both font-scale exemptions, preserved KPress prose-relative code and unrelated unhighlighted-source line geometry. Matching reserved-height golden regenerated through actual session; focused token/geometry checks pass. Final installed-wheel computed-size/jump QA remains coordinator acceptance.
