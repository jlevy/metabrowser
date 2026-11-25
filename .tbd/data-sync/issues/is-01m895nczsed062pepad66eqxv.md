---
type: is
id: is-01m895nczsed062pepad66eqxv
title: "PR #830 B2: HOLD_PLACE_MIN_PX comment gives whole-pixel scrolling as general"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m895natnk2hpvt6ftqmkeejf
hold: null
hold_until: null
created_at: 2026-11-25T10:57:43.926Z
updated_at: 2026-11-25T10:57:46.307Z
started_at: 2026-11-25T10:57:46.301Z
---
Low. src/metabrowser/builtin_plugins/diff/diff-view.js:4575-4581: the comment says the pane's scroll position takes whole pixels, which holds at DPR 1 (forced by tests/dom/chrome-session.mjs:177); Chrome takes half pixels at DPR 2. Say so, and why 1 px is kept: a 1/DPR threshold would bring the overshoot back on a coarser scroller (WebKit unmeasured). Review: https://github.com/jlevy/metabrowser/pull/830#pullrequestreview-6056253438
