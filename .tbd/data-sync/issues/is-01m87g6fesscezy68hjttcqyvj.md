---
type: is
id: is-01m87g6fesscezy68hjttcqyvj
title: Omit redundant navigation on the selected sidebar branch chip
kind: bug
status: in_progress
priority: 2
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/789
    at: 2026-11-24T19:30:06.530Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys615s2mfvbc93c9g2pac
hold: null
hold_until: null
created_at: 2026-11-24T19:23:20.396Z
updated_at: 2026-11-24T19:30:06.534Z
started_at: 2026-11-24T19:24:32.999Z
---
The branch or tag chip beside the revision chooser names the source already being viewed. Its own menu should offer copy and the corresponding external link when available, and omit View this branch or tag in that context. The adjacent chooser and other branch menus should still offer navigation to other targets.
