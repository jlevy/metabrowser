---
type: is
id: is-01m7hdmr9tdz8c3xt1dtzw7d8y
title: "PR #463 A8: IGNORED_ROW sleeps 200 ms instead of waiting for the hold's animation"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjqx287ha000smyytqswb
hold: null
hold_until: null
created_at: 2026-11-16T05:35:24.985Z
updated_at: 2026-11-16T05:48:03.125Z
started_at: 2026-11-16T05:48:02.744Z
closed_at: 2026-11-16T05:48:03.124Z
close_reason: "Fixed in 6c0bd6f1f: IGNORED_ROW awaits the row's animations' finished; test_files_tab_chrome passes."
resolution: null
duplicate_of: null
---
tests/dom/files-tab-chrome.mjs:861. Severity: Low. PR #463, Review A round 1: https://github.com/jlevy/metabrowser/pull/463#pullrequestreview-5915439143
