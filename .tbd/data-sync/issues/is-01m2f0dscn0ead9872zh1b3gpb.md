---
type: is
id: is-01m2f0dscn0ead9872zh1b3gpb
title: "PR #113 review R1: re-selecting the failed path takes the fragment-only branch and never refetches"
kind: bug
status: in_progress
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m2f0dryv9qmyp9y6g1sc4gwq
created_at: 2026-09-14T03:47:27.243Z
updated_at: 2026-09-14T03:51:17.764Z
---
PR #113 review R1 (Medium). src/metabrowser/static/app.js:7535-7540 (applyNavigationTarget), app.js:7504-7506, src/metabrowser/static/search-palette.js:586-588. After a selection fails (unreachable or error), opening the same path returns pathChanged:false, the fragment-only branch returns {status:'opened'} and selectFile never runs; the pane keeps 'Metabrowser isn't reachable' until the event stream reconnects (backoff cap 60 s) and Quick File closes as if it opened. Fix: take the fragment-only branch only when the pane holds or is loading that path (pane.holds(path) in the navigation.js lifecycle), otherwise call selectFile; add a session case that fails before the fix.
