---
type: is
id: is-01m7k6w6hj2p10bfr9zkd20c4x
title: The Files filter menus' counts read 0 while the navigation tallies are unknown, and an open File type menu keeps 0 when they arrive
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys3bp2ndx4v4m26exf0hz
created_at: 2026-11-16T22:15:37.777Z
updated_at: 2026-11-20T17:08:57.837Z
---
Found by the mb-h3hc audit of the Files nav panel (2026-11-16), measured in headless Chrome 152 on this repository at 1280x900 in the default 300 px pane.

The Modified within and File type menus' counts come only from the server's pass over every file (/api/tree?depth=0, the navigation tally), which the page asks for 500 ms after the tree and which takes half a second to seconds. Until it answers, every count reads 0: at the moment the totals line had settled, the menus read "Live 0", "Past hour 0", "Documentation 0", "Code 0"; four seconds later "Live 1", "Past hour 1,778", "Documentation 452", "Code 8,840". A 0 is a wrong figure, not a pending one.

With the File type menu open when the tally arrives, its counts stay 0 until the menu is reopened: fetchRootSummary patches only the Modified within counts in an open menu (patchOpenRecencyTallyCounts) and rebuilds the bar only when no menu is open. Measured with the tally held 3 s: the menu opened at 388 ms reading 0 for every type, and no frame changed through 5.9 s.

This does not move the Files panel: the menus are overlays and closed at load, and the open menu's box (225 x 180 px) did not change. It is the same principle as mb-h3hc: a count still being filled in should be the shell's pending placeholder (.tally-pending, after .mb-delayed-loading's quiet period) in the place its figure will take, and fill in place, including in an open menu (docs/design-system.md, "Loading States Are Shapes, Not Sentences", "Filters Say What They Do Not Know").
