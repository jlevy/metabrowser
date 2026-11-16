---
type: is
id: is-01m7hdapg56ynkb1p45ry02vxb
title: "PR #457 A6: Help's single-chord keycap has no hidden spoken phrase"
kind: task
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcje01mnwqrrmfa3d3b88g
hold: null
hold_until: null
created_at: 2026-11-16T05:29:55.459Z
updated_at: 2026-11-16T06:13:18.039Z
started_at: 2026-11-16T05:30:02.796Z
closed_at: 2026-11-16T06:13:18.038Z
close_reason: "fixed in 6072e01: a lone chord keycap gets the hidden phrase and aria-hidden glyph; pinned in keyboard-help-behavior.js. VoiceOver not run. Disposition: https://github.com/jlevy/metabrowser/pull/457#issuecomment-6908902070"
resolution: null
duplicate_of: null
---
Suggestion. PR #457 review A (https://github.com/jlevy/metabrowser/pull/457#pullrequestreview-5915398035). tests/dom/keyboard-help-behavior.js:660 pins spoken null; keyboard-shortcuts.js:500-506; docs/design-system.md:2095. Coordinator decision: give a single-chord keycap the hidden spoken phrase and hide the glyph from AT.
