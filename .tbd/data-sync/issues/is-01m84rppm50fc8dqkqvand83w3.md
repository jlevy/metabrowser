---
type: is
id: is-01m84rppm50fc8dqkqvand83w3
title: "PR #761 A1: the cores walk takes the share between the page's asks, so a walk longer than one hour's share holds the prefetch far below its caps for hours"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-22-pull-request-update-cadence.md
labels: []
dependencies: []
parent_id: is-01m82h0qrnw9vg6vrj597asgpv
created_at: 2026-11-23T17:54:17.348Z
updated_at: 2026-11-23T20:48:44.895Z
closed_at: 2026-11-23T18:55:49.245Z
close_reason: "Fixed in 0ace3fe37 on claude/catalog-share-order (PR #761), per the owner's option 1: pull_prefetch.reserved keeps one scan's records (RECORDS_PER_SCAN, at most the hour's room) for an idle lane a page asked for within ASKED_WITHIN_S (150 s, the panel's longest gap between asks plus a scan's run; tests/test_github_pull_prefetch.py pins the sum). The B1 test again pins #737's order, and test_a_walk_longer_than_an_hours_share_leaves_the_prefetch_its_records_every_hour runs a walk across three hours' roll (records read 9, 12, 12). Review A's model at 5,000 rows: records/h 7,2,2,2 before, 9,11,12,12 after."
resolution: null
duplicate_of: null
---
Review A1 (Medium) of PR #761: https://github.com/jlevy/metabrowser/pull/761#pullrequestreview-6026703603 (review A, senior, round 1, head 3f6e1a0c6).

pull_prefetch.reserved counts a lane only while lane.queue or lane.running is set (pull_prefetch.py:283). A lane has work for seconds per ask; the page asks once per published scan and after a rest, while the cores walk asks every CORE_BUSY_RETRY_MS when admitted and at most SLOW_POLL_MS (30 s) after a hold. Between asks the reserve is 0 and the walk spends the share; a later ask is refused at _governor and request_prefetch clears its records (pull_prefetch.py:345-351), so it reserves nothing either. As the rolling hour frees minutes the walk takes them first. For a walk longer than one hour's share (more than about 800 rows) the prefetch is held far below its caps for the walk's whole length, not "until the hour rolls" as the plan (:394-395), the reserved docstring and test_an_idle_lane_leaves_the_walk_the_rest_of_the_share say. That test now asserts the opposite of what review B1 of #737 asked to pin (the walk spends first and the prefetch's next record is still admitted).

Modelled, not measured (attic/sim_share.py in the review worktree, driving the production gh_budget.admission/spent/speculative and pull_prefetch.reserved on a real Lane; scans every 120 s, 7 missing records then 1 changed record a scan): 5,000 rows, records read per hour 7, 2, 2, 2 (28 refused an hour) against main's 12, 12, 12, 12; the walk 16, 80, 88, 88 batches an hour, 353 of 625 left after 4 h. Scans every 60-300 s with 1-3 changed records: 1-9 records an hour after the first. 800 rows: 8, 8, 12, 12, walk done at 62 min.

Fix (the owner's choice): (1) an idle lane still reserves one scan's records, min(RECORDS_PER_SCAN, records left) x POINTS_PER_RECORD (model at 5,000 rows: 8, 10, 12, 12 records an hour; walk 3, 40, 28, 28); (2) the walk gets an hourly number of its own beside the share, inside the 300 ceiling; (3) accept and state the multi-hour cost in the plan, the docstring, the test and changelog.d/mb-ztsq.md, and record the decision under the plan's open question. Add a test of a walk longer than one share across the hour's roll with the page asking on a scan cadence.
