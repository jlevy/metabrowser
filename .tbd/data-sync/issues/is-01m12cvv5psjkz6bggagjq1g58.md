---
type: is
id: is-01m12cvv5psjkz6bggagjq1g58
title: "PR #86 review R6: tabindex=-1 left on shared #tree-content after teardown"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m12cv7mskztpn9mrxcrdfm75
created_at: 2026-08-27T19:59:01.301Z
updated_at: 2026-08-27T19:59:01.301Z
---
src/metabrowser/static/git-panel.js:1034. Panel writes tabindex on shell-owned #tree-content and teardown() never removes it. Restore in teardown(). PR #86 comment 3873347053
