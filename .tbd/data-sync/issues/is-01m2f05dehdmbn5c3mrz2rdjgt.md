---
type: is
id: is-01m2f05dehdmbn5c3mrz2rdjgt
title: "PR #112 review S1: assert earlyNavigations in the early-focus test"
kind: bug
status: closed
priority: 4
version: 3
labels: []
dependencies: []
parent_id: is-01m2f05257wwkdtjwanq4bd016
created_at: 2026-09-14T03:42:52.880Z
updated_at: 2026-09-14T03:45:32.305Z
closed_at: 2026-09-14T03:45:32.304Z
close_reason: "Fixed in f67c6769: asserts attaching opens nothing and the first Down opens only the next row; fails on a scratch copy that navigates on adoption."
resolution: null
duplicate_of: null
---
PR #112 suggestion. tests/dom/tree-keyboard-navigation-behavior.js:617 collects earlyNavigations but never asserts it. Assert attaching navigates nothing and the first Down opens exactly the next row.
