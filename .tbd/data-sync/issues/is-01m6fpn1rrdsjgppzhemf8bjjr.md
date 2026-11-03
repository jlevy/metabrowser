---
type: is
id: is-01m6fpn1rrdsjgppzhemf8bjjr
title: "PR #281 D2: request_commit_fetch drops a refused attended job, so a commit page says the origin lacks a commit whose fetch never ran"
kind: bug
status: closed
priority: 3
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6fpn0yb9yn4kakx1qp787e4
hold: null
hold_until: null
created_at: 2026-11-03T03:18:41.175Z
updated_at: 2026-11-03T04:10:44.136Z
started_at: 2026-11-03T03:50:29.293Z
closed_at: 2026-11-03T04:10:44.135Z
close_reason: "Fixed in 34d4ad76: /api/source/refresh {for: commit} carries pull_refresh; describeMissingCommit says the pull request's refresh was not queued. Route shape changed (routes map, command-line guide, git architecture). Confirmed by test_a_commit_fetch_the_queue_has_no_room_for_says_so_beside_the_mirrors, the recording's commit_unqueued_* from the real session, and the session step pinned in cli-ui-source-freshness. CI 41574482948 green."
resolution: null
duplicate_of: null
---
Low. src/metabrowser/mirror_refresh.py:841-845, src/metabrowser/static/source-freshness.js:583-614. Fix: carry the companion's answer in the /api/source/refresh envelope as pull_refresh and let describeMissingCommit say when it is too_many. Review: https://github.com/jlevy/metabrowser/pull/281#pullrequestreview-5746822976 (PR #281, head 7bef1356).
