---
type: is
id: is-01m7jj4p5abjdbgjb9n55sqbgt
title: "PR #476 A5: Layout paragraph says the header box is decided at first paint in every state and omits the refresh case"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7jgg4b9taqwxcfevgd9c6gc
hold: null
hold_until: null
created_at: 2026-11-16T16:13:15.817Z
updated_at: 2026-11-16T17:10:06.361Z
started_at: 2026-11-16T16:13:22.255Z
closed_at: 2026-11-16T17:10:06.360Z
close_reason: "Fixed in de4118672: Layout leads with the labels-row exception, names the refresh case (first label gained or last lost moves the tab bar 26 px), and says where a cold page can still move; the CHANGELOG header entry names the refresh case."
resolution: null
duplicate_of: null
---
Severity: Low. PR #476 Review A (round 1), finding A5: https://github.com/jlevy/metabrowser/pull/476#pullrequestreview-5923174293. References: docs/design-system.md:1584-1586, :1601-1605; CHANGELOG.md:139-141, :151-153.
