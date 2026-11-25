---
type: is
id: is-01m88tvfgck73ax8stdn1qpk3y
title: "One Refresh: the Pulls tab's Refresh also refreshes the open PR page, which loses its own"
kind: task
status: closed
priority: 1
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/827
    at: 2026-11-25T09:03:46.712Z
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-25T07:48:48.777Z
updated_at: 2026-11-25T12:13:15.620Z
started_at: 2026-11-25T07:50:06.503Z
closed_at: 2026-11-25T12:13:15.618Z
close_reason: "Merged in #827 (Pulls rows and the PR page)"
resolution: null
duplicate_of: null
---
Asked by the user: the PR page's own Refresh, on its Opened / updated row, duplicates the Refresh in the nav column. Remove the page's Refresh; pressing the nav column's Refresh refreshes the list and the open PR page together. Keep a way to refresh when the nav pane is hidden (the same keyboard shortcut), and keep what the page's Refresh did that nothing else does (a Fetch on a mirror, a refresh offered after an error or rate limit) reachable from the one Refresh or the status row.
