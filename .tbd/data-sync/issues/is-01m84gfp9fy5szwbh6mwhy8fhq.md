---
type: is
id: is-01m84gfp9fy5szwbh6mwhy8fhq
title: Pulls branch-chooser Chrome session focuses a row before the page has focus, so a toolbar refill before End moves focus to the filter
kind: bug
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10
labels:
  - ci
dependencies: []
parent_id: is-01m7wys615s2mfvbc93c9g2pac
hold: null
hold_until: null
created_at: 2026-11-23T15:30:38.999Z
updated_at: 2026-11-23T15:30:49.592Z
started_at: 2026-11-23T15:30:49.590Z
---
main red since b68cc9571: tests/test_ref_selector_pulls_chrome.py:213 assert (None, None) == (601, True) in chrome (3.13, 4/4) of run 45187239621 and chrome (3.14t, 4/4) of run 45197627733. Every layout assertion before it passed; the end, redrawn and home steps all read scrollTop 0 and no focused row, so End went to the filter box. Mechanism: step 3 of tests/dom/ref-selector-pulls-chrome.mjs focuses the first row with element.focus() in a headless page that is not focused and so fires no focusin; keepAcrossRefills therefore has no record of the row, and a Files toolbar refill (renderNavFilterBar, which the filter tallies run when the root summary arrives and while the index warms up) between that focus and the End key gives focus to its fallback, the filter box. Reproduced locally by calling renderNavFilterBar() between the focus and End: the same (None, None) with scrollTop 0. The session enabled focus emulation only from step 6. Fix: enable Emulation.setFocusEmulationEnabled before the first navigation, as a reader's page has focus; with it the injected refill keeps the row. The product keeps a reader's row across a refill (steps 6 and 7). Since the stack the test's server also acquires an origin store from https://github.com/octo/demo at start, a real network attempt and a gh call (gh guard 1 to 2), which changes the page's timing; inferred, not measured, as what exposed the race.
