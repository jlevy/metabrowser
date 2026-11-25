---
type: is
id: is-01m88dn141rvkdema7hwvf2jmb
title: "PR #811 A13: keep the URL in step for a link into a withheld fold"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m88dfdf96exb192c9gb46hfz
hold: null
hold_until: null
created_at: 2026-11-25T03:58:05.931Z
updated_at: 2026-11-25T03:59:45.265Z
started_at: 2026-11-25T03:59:45.263Z
---
Suggestion. diff-markdown.js 1745-1748 preventDefault + scrollIntoView leaves the fragment unchanged; set it after drawing. Review A of PR #811: https://github.com/jlevy/metabrowser/pull/811#pullrequestreview-6051579395
