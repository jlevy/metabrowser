---
type: is
id: is-01m7hhr36mmrjwfw662gmgngf6
title: "Release 0.13: previous-release performance comparison (v0.12.0 vs exact candidate)"
kind: task
status: in_progress
priority: 1
version: 4
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-16T06:47:08.755Z
updated_at: 2026-11-23T03:16:14.065Z
started_at: 2026-11-23T03:13:34.430Z
---

## Notes

2026-11-17 coordinator: renumbered from exp-088 to exp-099, which has since been used for an earlier candidate. Main contains exp-099 through exp-101. Reserve the next unused number after checking the parallel performance plan when the release candidate is pinned.

Use the installed-wheel control and candidate on one unchanged project-10 corpus with five interleaved runs for both backend and visible headed Chromium, as prescribed by the release checklist. The prior comparable run (exp-034) used a quiet Linux cloud container with 1-minute load below 1.1. On 2026-11-22 the shared Mac's 1-minute load exceeded 200 and the prior Linux runner was unavailable. Exclude timings under those conditions.
