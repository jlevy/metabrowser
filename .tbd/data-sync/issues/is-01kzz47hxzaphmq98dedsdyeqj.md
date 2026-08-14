---
type: is
id: is-01kzz47hxzaphmq98dedsdyeqj
title: "PR #35 review R8: rowIsVisible stops its ancestor walk at the tree root"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzz46ttyre78pjmkxynpfh3z
created_at: 2026-08-14T03:14:42.750Z
updated_at: 2026-08-14T03:32:04.009Z
closed_at: 2026-08-14T03:32:04.008Z
close_reason: "Fixed in 78ee53e: rowIsVisible walks past the tree root so a hidden tab panel hides its rows."
---
tree_keyboard_navigation.js:59-74 returns true on reaching role=tree and never inspects ancestors above it, so rows in a hidden tab panel would count as visible once a second [data-tab-content] panel returns.
