---
type: is
id: is-01m884wd31hfbt8zbr1xg9266e
title: "PR page: the stack chip ends the row of state and ages, not the author's row"
kind: task
status: in_progress
priority: 3
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/815
    at: 2026-11-25T02:43:57.123Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-25T01:24:50.399Z
updated_at: 2026-11-25T02:43:57.125Z
started_at: 2026-11-25T01:27:02.088Z
---
The owner asked (2026-11-24): on the pull request page, the stack icon under the PR number should sit on the row with the state and ages ("Draft · Opened 3h ago · updated 18m ago"), not on the author's row ("jlevy wants to merge ...") below it. mb-cf0l put the chip at the end of the author's row; this moves it up one row, keeping what mb-cf0l and mb-ne91 guarantee: the header's box is decided at first paint, and a chip arriving from its own /stacks answer moves nothing.
