---
type: is
id: is-01m898r3v65whkf6yf8gqksc0z
title: Pulls tab return may drift a plain reading place when rows stand at other heights than when the scroll was saved
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
created_at: 2026-11-25T11:51:38.593Z
updated_at: 2026-11-25T11:51:38.593Z
---
Found in review of #827, not reproduced. The #827 fix (pulls-panel.js setShown rebase of revealedPlace; main-tabs.js markMainTabLanding re-sets the saved scroll only if routeChanged moved it) covers a row a reveal placed. A plain reading place (the first row in view, no reveal) is kept from the shell's restored scrollTop on show, which may stand elsewhere once rows placed at ROW_ESTIMATE_PX are measured or stacks regroup while the tab is hidden. Check in Chrome whether returning to the Pulls tab after a regroup keeps the first row in view where the reader left it.
