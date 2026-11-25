---
type: is
id: is-01m88nc4g3hy55mcxfd1sk8fhr
title: "Pulls row: a short title still takes two lines"
kind: bug
status: closed
priority: 1
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/827
    at: 2026-11-25T09:03:41.165Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
hold: null
hold_until: null
created_at: 2026-11-25T06:13:03.104Z
updated_at: 2026-11-25T12:13:12.706Z
started_at: 2026-11-25T06:13:51.506Z
closed_at: 2026-11-25T12:13:12.700Z
close_reason: "Merged in #827 (Pulls rows and the PR page)"
resolution: null
duplicate_of: null
---
Reported by the user after #821 merged: a PR title that fits on one line still reserves two (the heading has a fixed height of 2lh). The title should take one line when it fits and wrap to at most two when it does not. Done when a one-line title's row is one title line shorter, the virtualized list places rows of both heights without overlap, gaps, or a jump while scrolling, and Chrome checks pin both heights.
