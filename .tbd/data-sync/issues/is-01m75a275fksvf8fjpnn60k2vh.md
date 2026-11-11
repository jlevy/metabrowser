---
type: is
id: is-01m75a275fksvf8fjpnn60k2vh
title: "PR #351 A5: updated age can repeat merged/closed age; exact time lost when hidden"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m75a1p5xdgrc0v0e1pxfpct9
hold: null
hold_until: null
created_at: 2026-11-11T12:41:58.702Z
updated_at: 2026-11-11T12:57:03.745Z
started_at: 2026-11-11T12:57:01.771Z
closed_at: 2026-11-11T12:57:03.744Z
close_reason: "fixed in 970dbbc0: updated age also dropped when it repeats the merged/closed age; its exact time joins that age's tooltip; headerAges asserts open, merged, closed"
resolution: null
duplicate_of: null
---
Low. pull-page.js:2982-2998. Drop on closed/merged repeat too; keep the exact updated time in the opened age's tip. PR #351, review A (https://github.com/jlevy/metabrowser/pull/351#pullrequestreview-5855489961).
