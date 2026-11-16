---
type: is
id: is-01m7hhgp12y2bxnb0m96ebx78s
title: "PR #474 A4: status-sentence boundary of count summaries is undecidable from the doc"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hg857dzfenxr1hee0jd9ka
hold: null
hold_until: null
created_at: 2026-11-16T06:43:05.889Z
updated_at: 2026-11-16T07:10:05.566Z
started_at: 2026-11-16T06:43:14.316Z
closed_at: 2026-11-16T07:10:05.565Z
close_reason: "fixed in 0603cfa3f: count-summary definition states the band/summary-line/remark criterion; folder header strip named"
resolution: null
duplicate_of: null
---
Low. docs/design-system.md:416-418, :446-447, :450-452; search-controller.js:353-357; app.js:6080, :6639-6641. Fix: write the criterion into the definition and name the folder header strip in the row-metadata bullet. Review A round 1 on PR #474: https://github.com/jlevy/metabrowser/pull/474#pullrequestreview-5915978133
