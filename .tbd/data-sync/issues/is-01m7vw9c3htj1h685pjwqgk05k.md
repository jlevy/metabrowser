---
type: is
id: is-01m7vw9c3htj1h685pjwqgk05k
title: "Branch chooser: a branch with an open pull request shows the pull request (number, title, state) in the menu"
kind: feature
status: closed
priority: 2
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/651
    at: 2026-11-20T17:01:23.824Z
delegate: claude-code@spud10.local
labels:
  - linear
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T07:03:44.991Z
updated_at: 2026-11-20T17:01:23.826Z
started_at: 2026-11-20T07:05:04.264Z
closed_at: 2026-11-20T09:35:02.824Z
close_reason: "Landed in #651: the branch chooser shows each branch's pull requests"
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 35cbbe3f-eaba-49eb-9063-f5c2ae58ac96
    linked_at: 2026-11-20T16:53:03.275Z
---
Owner, 2026-11-20: 'The branch chooser in the files view seems to allow you to select branches by pull request, or at least link to that from a PR, but in the menu dropdown, it only shows the branch names. If a branch corresponds to a pull request, we should show the pull request as well.'
