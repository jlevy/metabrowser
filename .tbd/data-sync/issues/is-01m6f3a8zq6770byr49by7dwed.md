---
type: is
id: is-01m6f3a8zq6770byr49by7dwed
title: Row cap and prefetch, measured
kind: task
status: in_progress
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m2h7jjgpzyfbf10238j32z6q
hold: null
hold_until: null
created_at: 2026-11-02T21:40:45.174Z
updated_at: 2026-11-03T04:35:55.502Z
started_at: 2026-11-03T00:48:47.046Z
---
In a real browser: what the cap costs to render and keep, whether windowing is needed, the local prefetch, and the verdict on starting the refresh at a mirror's open, per the plan's Performance table.

## Notes

2026-11-03, PR 285, headless Chrome 152 at 1,000 real rows of pallets/click: tab activation 60-70 ms as plain rows and 14-23 ms with content-visibility:auto, so no windowing; a window 7-8 ms; a held key 0.3-0.6 ms a step at any size. Refresh at a mirror's open: adopted after the first tree (first row 1.001x, mirror refresh 0.998x, nine pairs); at page start 1.09-1.14x, rejected. Numbers beside WINDOW_ROWS in pulls-panel.js.

2026-11-03 (PR #285 addressing): B3's poll change: the top window with its tag, the whole held range re-read once only for another list file (fetched_at, count, reader, source, complete, truncated). One full read per completed refresh remains, since a refresh always writes a new fetched_at; the route's tag would have to name the held range (layer 1) to avoid it.
