---
type: is
id: is-01m7hdakxv59vm3sn0kzyz3cm0
title: "PR #457 A2: a held Ctrl+P falls through to the browser default after the first walk"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcje01mnwqrrmfa3d3b88g
hold: null
hold_until: null
created_at: 2026-11-16T05:29:52.826Z
updated_at: 2026-11-16T06:13:16.513Z
started_at: 2026-11-16T05:30:01.115Z
closed_at: 2026-11-16T06:13:16.511Z
close_reason: "fixed in 6072e01: both chords repeat and consume a repeat without walking; pinned by pulls-nav-session.js and the Chrome check's held press. Disposition: https://github.com/jlevy/metabrowser/pull/457#issuecomment-6908902070"
resolution: null
duplicate_of: null
---
Low. PR #457 review A (https://github.com/jlevy/metabrowser/pull/457#pullrequestreview-5915398035). src/metabrowser/static/pulls-nav.js:389,405 repeat false; keyboard-shortcuts.js:1356 skips repeats before matching; tests/dom/pulls-nav-session.js:491. Fix: consume repeats without walking.
