---
type: is
id: is-01m7qyd1pqw0w2m51k7bzqjc4h
title: "Chrome flake: nav reveal 'a changed file clicked: its row stays in view' on the Pulls tab ends with the row out of view"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-18T18:23:44.853Z
updated_at: 2026-11-18T18:23:44.853Z
---
Main's CI at 3c864fe88 (#562's merge), chrome (3.13, 1/4): tests/test_nav_reveal_chrome.py failed phase 'a changed file clicked: its row stays in view' with {tab: pulls, address: /pull/106/files/src/app/plugins/github/mod_040.py, row: {selected: true, inView: false, at: [1537,1561,108,674,48], clip: null, travelling: false}, focusInNav: true}. The row's top is 1537 px in a 674 px pane: it is selected but never scrolled into view. A different phase from mb-551m (#556, a long folder's page by its address). Find what scrolls the pull request's changed-files tree after a click and why it didn't here.
