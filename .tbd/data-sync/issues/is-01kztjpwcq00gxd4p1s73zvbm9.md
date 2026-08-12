---
type: is
id: is-01kztjpwcq00gxd4p1s73zvbm9
title: Keep navigation tally status aligned with its inventory snapshot
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-09-nav-filter-controls.md
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-12T08:51:32.885Z
updated_at: 2026-08-12T09:04:54.399Z
closed_at: 2026-08-12T09:04:54.399Z
close_reason: Implemented with regression coverage; full make verify passed on 2026-08-12.
---
api_tree snapshots entries before off-loop navigation tallies, but reads tally_cache_status after the await. If the walker finishes during tally computation, a partial snapshot can be labeled done and the client may stop polling without a completion refresh. Capture and return the status from the same pre-worker snapshot epoch, with a regression test.

## Notes

api_tree and api_recent now capture tally_cache_status before their off-event-loop snapshot work, so a partial inventory cannot be paired with a newer done status. Regression tests force the scan-to-done transition during worker execution. Full make verify passed on 2026-08-12.
