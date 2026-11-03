---
type: is
id: is-01m6g1xpxacj8ff1ckwbbq06n0
title: "PR #285 C5: the /pulls landing is right only after a reload"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6g1x4rv0qbdqdqdz64p3qn0
hold: null
hold_until: null
created_at: 2026-11-03T06:35:39.303Z
updated_at: 2026-11-03T07:05:04.141Z
started_at: 2026-11-03T07:04:23.577Z
closed_at: 2026-11-03T07:05:04.140Z
close_reason: "fixed in 2cfed240: followLanding reads the list again until it has something to say; session story on three new recordings"
resolution: null
duplicate_of: null
---
mountPullsLanding (pulls-panel.js:1767-1788) reads the list once with limit=0 at mount; on a first visit the refresh has not failed yet, so it says Select a pull request and never reads again. Follow the list until it has something to say; add a session step from absent to the failure. Review: https://github.com/jlevy/metabrowser/pull/285#pullrequestreview-5747624823 (severity Low).
