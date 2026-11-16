---
type: is
id: is-01m7hdmms8e99pz87m3k4xtrx1
title: "PR #458 A2: dead scroll reset for a returning toolbar, still pinned by a browserless test"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjeyyagvt3h7zcvvssfks
hold: null
hold_until: null
created_at: 2026-11-16T05:35:21.383Z
updated_at: 2026-11-16T06:16:20.366Z
started_at: 2026-11-16T05:35:28.808Z
closed_at: 2026-11-16T06:16:20.363Z
close_reason: "Fixed in 3ed205983 on PR #458; disposition reply https://github.com/jlevy/metabrowser/pull/458#issuecomment-6908956491"
resolution: null
duplicate_of: null
---
Medium. Review A https://github.com/jlevy/metabrowser/pull/458#pullrequestreview-5915435915. src/metabrowser/static/main-tabs.js:362-371, :357-358; tests/dom/preview-pane-state-session.js:1526-1533. .nav-toolbar no longer scrolls, so the returning && slot.scrollLeft > 0 branch is dead. Fix: delete the branch and its comment, delete the 'a scrolled toolbar comes back at its start' assertion, qualify :357-358 to 'at one height while each is one line'.
