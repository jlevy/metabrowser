---
type: is
id: is-01m12cvv5psjkz6bggagjq1g58
title: "PR #86 review R6: tabindex=-1 left on shared #tree-content after teardown"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:59:01.301Z
updated_at: 2026-08-27T20:21:16.983Z
closed_at: 2026-08-27T20:21:16.983Z
close_reason: "Fixed in 3ad9113 on codex/unbounded-git-history (PR #86)"
resolution: null
duplicate_of: null
---
src/metabrowser/static/git-panel.js:1034. Panel writes tabindex on shell-owned #tree-content and teardown() never removes it. Restore in teardown(). PR #86 comment 3873347053
