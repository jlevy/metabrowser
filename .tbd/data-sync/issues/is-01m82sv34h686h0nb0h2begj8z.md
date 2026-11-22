---
type: is
id: is-01m82sv34h686h0nb0h2begj8z
title: Center the folder overview with a collapsed README
kind: bug
status: in_progress
priority: 3
version: 3
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/711
    at: 2026-11-22T23:36:17.685Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m82hy6zdk5e5zzmsan8xhw6q
hold: null
hold_until: null
created_at: 2026-11-22T23:35:40.943Z
updated_at: 2026-11-22T23:36:19.978Z
started_at: 2026-11-22T23:36:19.976Z
---
PR #711 reserves the README table-of-contents rail even after the document panel is collapsed, shifting the wide centered Overview about 9rem left. Condition the rail on an expanded panel and verify with a long README in Chrome. Independent review https://github.com/jlevy/metabrowser/pull/711#pullrequestreview-6015125473.
