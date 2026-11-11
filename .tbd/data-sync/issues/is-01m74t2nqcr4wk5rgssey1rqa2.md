---
type: is
id: is-01m74t2nqcr4wk5rgssey1rqa2
title: "PR #346 A4: automatic comparison attempt ignores the recorded outcome on every mount"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m74t21pvwps4wh189z73rspr
hold: null
hold_until: null
created_at: 2026-11-11T08:02:36.395Z
updated_at: 2026-11-11T08:21:20.398Z
started_at: 2026-11-11T08:02:47.551Z
closed_at: 2026-11-11T08:21:20.397Z
close_reason: "Fixed in 9c625f4e: comparisonHeld holds the automatic attempt for Retry changes when last_refresh is rate_limited with a future reset_at, or lender_missing/git_failed/fetch_failed not older than the record; refreshing_elsewhere is transient and not held. Confirmed by the session's held steps (lender_missing, rate limit until it lifts)."
resolution: null
duplicate_of: null
---
Low. fetchSelectedChanges (pull-page.js:1412-1426) never reads envelope.last_refresh, so each mount repeats a retry:true job after lender_missing or during a rate limit (server guards bypassed, pull_route.py:603-608; companion.refresh at checkout.py:406). Fix: hold the automatic attempt and offer Retry when rate_limited reset_at is in the future or an acquisition failure is newer than the record. Review: https://github.com/jlevy/metabrowser/pull/346#pullrequestreview-5855482052 (PR #346, review A, round 1).
