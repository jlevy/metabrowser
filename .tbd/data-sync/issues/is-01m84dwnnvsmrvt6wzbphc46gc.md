---
type: is
id: is-01m84dwnnvsmrvt6wzbphc46gc
title: "main red at b68cc9571: ref selector Pulls rows not placed by their own height in Chrome (None, None)"
kind: bug
status: in_progress
priority: 1
version: 3
delegate: claude-code@spud10
labels:
  - ci
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-23T14:45:18.650Z
updated_at: 2026-11-23T15:23:51.517Z
started_at: 2026-11-23T15:03:21.833Z
---
main's CI run 45187239621 (push of b68cc9571, the #747 merge) failed chrome (3.13, 4/4): tests/test_ref_selector_pulls_chrome.py:213 test_rows_with_a_pull_request_are_placed_by_their_own_height_in_chrome asserted (None, None) == (601, True): the probe read no row placement at all. mb-tay7 (closed) fixed a branch chooser that lost scroll and focus when the Files toolbar redrew between a scroll and its event; #747 changed the folder and pull cadence. Find why the probe read nothing, then fix it or revert.

## Notes

Mechanism: a headless page is unfocused until its first CDP key, so no focusin fired for step 3's programmatic focus(). A Files toolbar refill (renderNavFilterBar, e.g. tallies arriving) between that focus and End made keepAcrossRefills fall back to the filter box, so End moved the caret. Reproduced locally by inserting renderNavFilterBar() there. Fix (PR 755): focus emulation from page load, and step 3 always refills before End. Product unaffected: a reader's page is focused. Main's run 45197627733 failed the same way (chrome 3.14t).
