---
type: is
id: is-01m78a9atxnxy4y2qk7axhs9hv
title: "PR #374 A3: activateScope() accepts a permanent scope and reverses the documented precedence"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m78a8v8t7c3wp1sv22v0gqa8
hold: null
hold_until: null
created_at: 2026-11-12T16:43:35.132Z
updated_at: 2026-11-12T16:43:44.120Z
started_at: 2026-11-12T16:43:44.119Z
---
Low. Review A on PR #374: https://github.com/jlevy/metabrowser/pull/374#pullrequestreview-5871435989. src/metabrowser/static/keyboard-shortcuts.js:571-579 accepts view-tabs or global as an activation; activeLayers() (lines 492-510) then lists it above global, breaking the stack-P over Preview-P precedence (comment at lines 487-491). Fix: throw a TypeError in activateScope() when PERMANENT_SCOPES.includes(scope); add a rejects() case beside the view-tabs block in tests/dom/keyboard-shortcuts-behavior.js. Deferred to layer 3 of stack #376 (branch claude/keys-3-reveal, bead mb-04dn), which is extending keyboard-shortcuts.js and has taken this on.
