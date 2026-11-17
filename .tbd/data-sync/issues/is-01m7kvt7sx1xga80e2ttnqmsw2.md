---
type: is
id: is-01m7kvt7sx1xga80e2ttnqmsw2
title: "PR #496 review B2: the main-state rule does not cover a fallback run that is also unfinished"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kvt6zsgb9m5xpanazw7prr
created_at: 2026-11-17T04:21:33.629Z
updated_at: 2026-11-17T04:23:03.440Z
closed_at: 2026-11-17T04:23:03.439Z
close_reason: "Fixed in 008a68b9: one page of push runs, newest first; first run with a finished attempt gives the state; a rerun counts by its previous attempt, an unfinished first attempt is passed over; none in the page is red. Test row and mb-oz36 add two runs in progress, a queued run, and no finished attempt."
resolution: null
duplicate_of: null
---
plan:255-258, :665. Two runs in progress, or a queued run; add them to the test row and mb-oz36.
