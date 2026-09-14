---
type: is
id: is-01m2f00gj8x117hjsmeg9cjhrr
title: "PR #111 review R1: 'j opens the row it lands on' tree test assertion cannot fail"
kind: bug
status: closed
priority: 3
version: 3
labels: []
dependencies: []
parent_id: is-01m2f006s6gd550e7knf1qw3m6
created_at: 2026-09-14T03:40:12.231Z
updated_at: 2026-09-14T04:22:36.770Z
closed_at: 2026-09-14T04:22:36.769Z
close_reason: "Fixed in e277e7a9 (PR #111): j check requires exactly one new navigation ending in folder:empty; confirmed failing with j unbound in a scratch copy."
resolution: null
duplicate_of: null
---
PR #111 review R1 (Low). tests/dom/tree-keyboard-navigation-behavior.js:434: the previous step already opened folder:empty, so navigationCalls.at(-1) === 'folder:empty' holds before j is sent. Fix: record navigationCalls.length before j and assert it grew by one with folder:empty last.
