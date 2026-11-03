---
type: is
id: is-01m6fcnr8wxeww1pwwc5w4nhp1
title: "PR #280 C1: The first Split decision is measured before the pane has its resting width"
kind: bug
status: closed
priority: 1
version: 2
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m6f3nkg482640stjteqx3fvw
created_at: 2026-11-03T00:24:18.459Z
updated_at: 2026-11-03T01:06:43.335Z
closed_at: 2026-11-03T01:06:43.334Z
close_reason: "fixed in ca450430: one layout on each fresh narrow load in headed Chrome, wide panes byte-identical"
resolution: null
duplicate_of: null
---
Medium. diff-view.js:1480-1482: a narrow pane draws Split and throws it away on a fresh load. Review: https://github.com/jlevy/metabrowser/pull/280#pullrequestreview-5745304651
