---
type: is
id: is-01m0prnmk4ptv52f8qqp9c0jvf
title: "PR #72 review R11: the new tests assert source strings, one asserting the absence of an old spelling"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m0prm49eb29wxywrqtdck27b
created_at: 2026-08-23T07:34:27.683Z
updated_at: 2026-08-23T08:07:31.837Z
closed_at: 2026-08-23T08:07:31.836Z
close_reason: Fixed in 552a41d. Dropped the assertion that the old empty-chrome spelling is absent, replaced the 1200-char window with a helper bounded by the next top-level function, and added positive assertions for the scoping and the chip-box coupling. Seven tests, all passing.
---
tests/test_skeleton_reserves_its_height.py:60 asserts 'chromeHtml: ""' not in block, which passes for any other spelling of the same bug; :70 slices a magic 1200-char window; app.index() raises ValueError rather than failing an assertion if a function is renamed. Fix: keep the positive assertions, drop the negative one, and bound the slice by the next function rather than by 1200.
