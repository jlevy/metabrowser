---
type: is
id: is-01m6fe1ckcbrw57rg4hcj0mcch
title: "Decide the size of a diff's code: 13.6px from a token nothing defines, or the ramp's 12px"
kind: task
status: open
priority: 3
version: 1
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3nkg482640stjteqx3fvw
created_at: 2026-11-03T00:48:08.299Z
updated_at: 2026-11-03T00:48:08.299Z
---
--code-font-size is defined nowhere, so .diff-line and .diff-split-side read at their fallback 0.85rem, 13.6px, and follow the browser's root size. The ramp's --mono-block-font-size is 12px. Moving to it shrinks every diff on every page, which is the owner's decision. tests/test_design_vocabulary.py holds the exemption until then. From review A finding A8 on PR #280.
