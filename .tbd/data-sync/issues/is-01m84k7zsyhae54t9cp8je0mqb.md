---
type: is
id: is-01m84k7zsyhae54t9cp8je0mqb
title: "Pulls panel asks pulls-prefetch, pulls and pull-cores-prepare about once a second while prefetching: measure whether that cadence is intended"
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
created_at: 2026-11-23T16:18:52.348Z
updated_at: 2026-11-25T02:21:39.569Z
---
Seen in a 12-minute headless Chrome run against a live server on /pull/745 (2026-11-23 16:05-16:17Z): while the prefetch ran, the page sent GET /api/plugin/github/pulls-prefetch, GET /api/plugin/github/pulls and POST /api/plugin/github/pull-cores-prepare roughly once a second (server event log around 16:17:10-16:17:16). These are local requests, not GitHub calls. Find which loop sends them, whether its interval is a measured choice, and bound it if not. Evidence: attic/live-check/run-window-events.json in the attended-pull-watch worktree.
