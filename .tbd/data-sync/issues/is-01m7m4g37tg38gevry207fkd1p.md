---
type: is
id: is-01m7m4g37tg38gevry207fkd1p
title: "Pulls tab: rows flush left unless stacked; chevron sits left of the change line's values"
kind: feature
status: closed
priority: 2
version: 9
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/506
    at: 2026-11-20T17:05:34.517Z
delegate: claude-code@spud10.local
labels:
  - ui
  - pulls
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-17T06:53:18.445Z
updated_at: 2026-11-20T19:15:59.653Z
started_at: 2026-11-17T06:53:22.815Z
closed_at: 2026-11-17T07:36:29.916Z
close_reason: Done in jlevy/metabrowser#506 (claude/pulls-row-indent)
resolution: null
duplicate_of: null
extensions: {}
---
In the Pulls tab each pull request is three lines. The first two lines (title and metadata) are indented more than they need to be: they should sit flush at the list's left edge, and only a pull request that is part of a stack is indented (to show its place in the stack). With the extra indent gone, the chevron in the third line (the brief change line / diff summary) moves to the left of the values, with padding on its left and less padding on its right.
