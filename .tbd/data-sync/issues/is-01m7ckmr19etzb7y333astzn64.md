---
type: is
id: is-01m7ckmr19etzb7y333astzn64
title: Commits landing skips the HEAD check when a page is loading at the switch
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-14T08:44:04.008Z
updated_at: 2026-11-14T08:44:04.008Z
---
Found reviewing #423 (mb-78k2), pre-existing on main. ensureHistory returns at once on state.loading, so a switch to Commits while a page of history is on its way (for example the scroll reset replaying an evicted page 0) reads no HEAD at all, and the newest landing is answered from the walk as it is. After a checkout made while Commits was hidden, the list and pane then show the pre-checkout history and its newest commit until the next activation; they agree, so nothing is left unselected. Fix: let ensureHistory read HEAD whenever rows exist, even with a page loading (without rendering over the page), and supersede that page with refreshHistory({supersede: true}) when HEAD moved, as #423 does for a page that began during the read. Test in tests/dom/git-panel-behavior.js beside the 'moved, page loading' case.
