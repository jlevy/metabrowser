---
type: is
id: is-01m7n6v9tbv4yn1xeap5zz6ryq
title: "Diff summaries: measure route and git/gh timings and fix the dominant cost"
kind: task
status: closed
priority: 1
version: 8
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/522
    at: 2026-11-20T17:01:38.098Z
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
hold: null
hold_until: null
created_at: 2026-11-17T16:53:37.227Z
updated_at: 2026-11-20T19:15:59.912Z
started_at: 2026-11-17T16:53:43.377Z
closed_at: 2026-11-17T22:40:52.598Z
close_reason: "Measured (lane alternated 3.6-4.7 s record reads with GitHub list reads; checkout mode had no store) and fixed in #522, merged f55ab001e: Pulls rows' last line 40.6 s -> ~10 s on a fresh cache, 27.2 -> 8.1 s in the regression benchmark's pairs."
resolution: null
duplicate_of: null
extensions: {}
---
Measure, in a real browser and from metab, the routes behind the Pulls row change lines and the PR page Diff summary and the git/gh work under them; name the dominant cost and fix it. Record measurements beside the constants and in explorations/performance-loop/design-rule-measurements.md.
