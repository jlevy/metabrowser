---
type: is
id: is-01m6th4q8ppch1rc8h9varn3pt
title: Use one visible content gutter for Markdown and Source
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T08:14:02.005Z
updated_at: 2026-11-07T08:14:58.221Z
started_at: 2026-11-07T08:14:58.209Z
---
User reports rendered Markdown/card content flush against pane edge despite the previous left-alignment change. Apply the same visible outer gutter/padding to Source and rendered Markdown, aligned with the first display tab. Include standalone documents, the Overview README, wide TOC and narrow drawer behavior. Measure both outer surfaces and text inset so card padding cannot conceal a missing pane gutter; update the design documentation and verify installed build.
