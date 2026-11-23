---
type: is
id: is-01m84gfp9fy5szwbh6mwhy8fhq
title: Long-list branch-chooser Chrome session focuses a row before its page has focus, the race mb-nbyu fixed in the pulls session
kind: bug
status: closed
priority: 1
version: 4
delegate: claude-code@spud10
labels:
  - ci
dependencies: []
parent_id: is-01m7wys615s2mfvbc93c9g2pac
hold: null
hold_until: null
created_at: 2026-11-23T15:30:38.999Z
updated_at: 2026-11-23T16:13:18.088Z
started_at: 2026-11-23T15:30:49.590Z
closed_at: 2026-11-23T16:13:18.087Z
close_reason: "Fixed in #756 (6782fc318)"
resolution: null
duplicate_of: null
---
The pulls session's failure on main (assert (None, None) == (601, True)) was fixed by #755 as mb-nbyu: focus emulation before the first navigation, and a toolbar redraw before End. tests/dom/ref-selector-long-list-chrome.mjs has the same step 3 (element.focus() on the first row, then End, in a headless page with no focus, so no focusin and keepAcrossRefills has no record of the row) and #755 left it as it was. With renderNavFilterBar() injected between that focus and End, main's session fails with assert (None, None) == (2001, 'b-0000'). PR #756 gives it the same two changes; it passes locally. Not seen failing in CI.
