---
type: is
id: is-01m75z3hxm730mh6wjecfwra9f
title: "PR #354 A4: rate-limit next check at names reset_at, not when the page will ask"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m75z31wt2khnr26spwbyy984
hold: null
hold_until: null
created_at: 2026-11-11T18:49:42.579Z
updated_at: 2026-11-11T19:23:49.776Z
started_at: 2026-11-11T18:51:52.184Z
closed_at: 2026-11-11T19:23:49.776Z
close_reason: "fixed in bba07860: rateLimitLifts = max(reset_at, last attempt + window); text, hold and wake use it; page session rateLimited story"
resolution: null
duplicate_of: null
---
Low. pull-page.js describePull wording and untilHoldLifts: use max(reset_at, last attempt + window) and ask then. Review: https://github.com/jlevy/metabrowser/pull/354#pullrequestreview-5863835475
