---
type: is
id: is-01m7n30vypg674csbm2dm1h1zq
title: "Folder overview: a long README's table of contents fades in when scrolled back to the top, as on the README itself"
kind: bug
status: closed
priority: 2
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/517
    at: 2026-11-20T17:02:43.063Z
delegate: claude-code@spud10.local
labels:
  - ui
  - files
  - toc
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-17T15:46:45.332Z
updated_at: 2026-11-20T17:59:52.414Z
started_at: 2026-11-17T15:47:51.034Z
closed_at: 2026-11-17T17:48:56.602Z
close_reason: Done in jlevy/metabrowser#517 (claude/overview-readme-toc)
resolution: null
duplicate_of: null
extensions:
  linear:
    id: ddcb38b8-1023-4dc7-85b0-e34193ef64eb
    linked_at: 2026-11-20T17:59:52.413Z
---
On a folder overview page in the Files tab, when the README shown there is long and you scroll back to its beginning, the table-of-contents widget should fade in and appear as it does when viewing the README directly. Today it does not (the TOC behavior differs between the README embedded in the overview and the README opened on its own).
