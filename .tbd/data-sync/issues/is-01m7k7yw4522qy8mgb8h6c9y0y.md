---
type: is
id: is-01m7k7yw4522qy8mgb8h6c9y0y
title: In a narrow pane the Files rows can paint a frame before the filter bar fills and wraps, then move 30 px with it
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7k4tntv9my4ynk41w81g0sj
created_at: 2026-11-16T22:34:33.988Z
updated_at: 2026-11-16T22:34:33.988Z
---
Found by the mb-h3hc audit of the Files nav panel (2026-11-16), headless Chrome 152, 1280x900, with the navigation pane set to its 180 px minimum.

The shell ships the Files filter bar one line tall (37 px, the reserved toolbar slot), and filter-controls.js fills it. At 180 px the filled bar (Group by, Show ignored, the drawer chevron) wraps to two lines, 67 px. Usually the inline tree rows paint in the same frame as the filled bar, so no row moves; Chrome still records a 0.00256-0.00268 layout shift of the empty #tree-content, whose loading spinner is still hidden by .mb-delayed-loading. In one run of the tests/test_files_totals_stable_chrome.py fixture, the rows painted a frame first (57 ms), and the bar filled at 69 ms: the totals line and every row moved down 30 px, with a 0.00268 layout shift. On main's code the same race showed once at 180 px in dark (bar 30 px, rows 69 px together with the ignored-line move).

docs/design-system.md, "Regions Keep Their Boxes", exempts a navigation toolbar in a pane too narrow for it, so this is documented behavior, not a regression. It is still content arriving late and moving the view, which the owner's mb-h3hc rule says should never happen. The fix is H52 (mb-rxst): the server renders the bar's resting-state chips, so the bar has its wrapped height at first paint. tests/test_files_totals_stable_chrome.py starts first paint at the first frame with rows under a filled bar, so it does not catch this race; a fix should add that case.
