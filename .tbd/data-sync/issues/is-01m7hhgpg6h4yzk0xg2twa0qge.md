---
type: is
id: is-01m7hhgpg6h4yzk0xg2twa0qge
title: "PR #474 A5: test-only strings left in production modules"
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
created_at: 2026-11-16T06:43:06.373Z
updated_at: 2026-11-16T07:10:05.901Z
started_at: 2026-11-16T06:43:14.673Z
closed_at: 2026-11-16T07:10:05.900Z
close_reason: "fixed in 40ef87afd: recentFilteredTallyText and unread files/breakdown fields removed; tests join parts"
resolution: null
duplicate_of: null
---
Low. tree-filter-model.js:1173-1183, :1850; types.d.ts:1826; changed-files-tree.js:682-683; diff-model.js:432. Fix: remove recentFilteredTallyText and the unread files/breakdown fields; tests join the parts. Review A round 1 on PR #474: https://github.com/jlevy/metabrowser/pull/474#pullrequestreview-5915978133
