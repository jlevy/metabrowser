---
type: is
id: is-01m82s87jvewvbb1kp1a9kyt0k
title: "PR #709 A8: each ask returns the whole envelope"
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
hold: null
hold_until: null
created_at: 2026-11-22T23:25:22.899Z
updated_at: 2026-11-23T08:02:29.932Z
started_at: 2026-11-23T06:37:54.704Z
closed_at: 2026-11-23T08:02:29.920Z
close_reason: "Done in 0acc229f5 on claude/cadence-followups. The page's automatic ask names the record it shows (held = record_revision); POST pull-refresh then answers record_held in place of record when the server's record is that one, and the page keeps its record under the answer's verdict, or reads the route when it no longer holds that record (another revision, or a no_store difference). Measured 2026-11-23, median of 200 JSONResponse renders, three runs, load ~380: 344 KiB record 351,924 bytes / 1.70-1.72 ms whole vs 733 bytes / 0.006 ms held; 290 KiB record 296,962 bytes / 1.31 ms vs 733 bytes / 0.006 ms. Recorded beside refresh_answer_pull in pull_route.py. Goldens: cli-github-pull-refresh.txt (held.json step), cli-ui-github-pull-page, cli-ui-github-pulls-panel, cli-ui-github-checkout-comparison."
resolution: null
duplicate_of: null
---
Low in A, Medium in K (343 KB, 1.74 ms on loop per ask). sidekick.py. https://github.com/jlevy/metabrowser/pull/709#pullrequestreview-6015073163
