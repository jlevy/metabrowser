---
type: is
id: is-01m7hdz7xcraprsyxvgtxyc04x
title: "PR #464 A1: an address that keeps the current pull request reveals its row again (tabs, changed files)"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjm7dvfsqanbt2jtdyxfy
hold: null
hold_until: null
created_at: 2026-11-16T05:41:08.652Z
updated_at: 2026-11-16T06:28:45.483Z
started_at: 2026-11-16T05:41:16.034Z
closed_at: 2026-11-16T06:28:45.482Z
close_reason: "Fixed in 4f55a7e (revealPullAddress: a same-PR address tells the list and reveals nothing) and d711ab1 (Chrome setup); confirmed by nav-reveal-session.js steps and test_nav_reveal_chrome.py steps 11-12, which fail at 0b49516."
resolution: null
duplicate_of: null
---
High. Review A on PR #464 (https://github.com/jlevy/metabrowser/pull/464#pullrequestreview-5915452177). app.js:8788-8800 pushHref/replaceHref call mainTabs.reveal for every address, pulls-nav.js:276,291-293, pulls-panel.js:2881-2886 same-number branch runs showCurrent: another tab of the PR shown, or one of its changed files clicked or walked with J/K, reopens a closed stack and scrolls to the PR row. Coordinator: one-shot again intent; pushHref/replaceHref reveal only a different PR.
