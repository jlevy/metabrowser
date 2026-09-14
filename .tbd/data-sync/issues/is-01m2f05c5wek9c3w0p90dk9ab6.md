---
type: is
id: is-01m2f05c5wek9c3w0p90dk9ab6
title: "PR #112 review R1: focus-adoption and scope-activation guards are not pinned by tests"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m2f05257wwkdtjwanq4bd016
created_at: 2026-09-14T03:42:51.578Z
updated_at: 2026-09-14T03:45:31.687Z
closed_at: 2026-09-14T03:45:31.686Z
close_reason: "Fixed in f67c6769: replaced the vacuous nav-snapshot check with a durable-anchor tabIndex check after a repair and a focus-outside repair that leaves ArrowDown unhandled; each fails on a scratch copy with its guard removed."
resolution: null
duplicate_of: null
---
PR #112, Medium. Guards at src/metabrowser/static/tree-keyboard-navigation.js:306 (!anchorIdentity) and :340 (activeElement is a tree row) survive mutation: the suite passes with either removed. The check 'tree scope leaves with focus' at tests/dom/tree-keyboard-navigation-behavior.js:583-584 is vacuous because tree commands are Help-only, so snapshot('nav') is always empty. Fix: replace lines 580-584 with a durable-anchor tabIndex check after a repair and a focus-outside repair check that leaves ArrowDown unhandled.
