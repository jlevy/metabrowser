---
type: is
id: is-01m7tecxp471vedhc0jascx58a
title: Pulls list never reveals a pull request newer than the catalog once a poll brings it in
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-19T17:41:46.817Z
updated_at: 2026-11-19T17:41:46.817Z
---
From review A on #611 (L7, predates it): a pull request created after the last refresh, named by a navigation, gets 'not in this list'; when a later poll brings its row in, the note goes but the row is not revealed, because only a list's first poll reveals and the chase looks only at older numbers (pulls-panel.js createPullsController).
