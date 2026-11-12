---
type: is
id: is-01m78a9bcvecdntxzppev6c8zs
title: "PR #374 A4: dead chord branch in appendBinding() and chord wording in the design system"
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
created_at: 2026-11-12T16:43:35.706Z
updated_at: 2026-11-12T16:43:44.583Z
started_at: 2026-11-12T16:43:44.582Z
---
Low. Review A on PR #374: https://github.com/jlevy/metabrowser/pull/374#pullrequestreview-5871435989. describeBindings() (keyboard-shortcuts.js:262-272) gives every alternative one key and separators []; in appendBinding() (lines 297-334) the alternative.keys.length > 1 test (line 300) and the keyIndex > 0 separator branch with its + fallback (lines 318-326) never run. docs/design-system.md:196 still says 'For a chord or alternative, emit one .kbd per physical key'. Fix: render alternative.keys[0] directly, compute complex from presentation.visible.length > 1, reword design-system.md:196 to 'For alternatives, emit one .kbd per key'. Deferred to layer 3 of stack #376 (branch claude/keys-3-reveal, bead mb-04dn), which is extending keyboard-shortcuts.js and has taken this on.
