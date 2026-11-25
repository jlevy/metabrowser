---
type: is
id: is-01m898qss04w1v4zfes05aneas
title: "PR #838 A7: the Conversation card can say something untrue or link nothing"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m898q9z40pe69kyfzr97xxjv
hold: null
hold_until: null
created_at: 2026-11-25T11:51:28.280Z
updated_at: 2026-11-25T12:28:29.728Z
started_at: 2026-11-25T12:28:29.723Z
---
Low. pull-page.js:6724 and 8215-8219 draw the card whenever the hint matches: an empty slot when the pull request is in no known stack, and the stack guided review claim when another member carries it or the block cannot be read. Review: https://github.com/jlevy/metabrowser/pull/838#pullrequestreview-6057040965
