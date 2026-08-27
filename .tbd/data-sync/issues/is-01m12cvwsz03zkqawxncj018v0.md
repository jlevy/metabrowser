---
type: is
id: is-01m12cvwsz03zkqawxncj018v0
title: "PR #86 review R10: scrollTopForOrdinal mutates segmentStart despite query-shaped name"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:59:02.974Z
updated_at: 2026-08-27T20:21:17.010Z
closed_at: 2026-08-27T20:21:17.010Z
close_reason: "Fixed in 3ad9113 on codex/unbounded-git-history (PR #86)"
resolution: null
duplicate_of: null
---
src/metabrowser/static/git-history-window.js:298. Split the rebase into a named mutator or rename so mutation is visible at call sites. PR #86 comment 3873347844
