---
type: is
id: is-01m7hfbay8vwsget27a0g4y8mm
title: "PR #473 A1: heading tally numeral borrows --pull-number-weight"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7he951v8gwjt3ejjes5d4ab
hold: null
hold_until: null
created_at: 2026-11-16T06:05:13.542Z
updated_at: 2026-11-16T06:40:58.556Z
started_at: 2026-11-16T06:05:23.941Z
closed_at: 2026-11-16T06:40:58.555Z
close_reason: "A1 fixed in 4d659021c: --count-numeral-weight token"
resolution: null
duplicate_of: null
---
Medium. src/metabrowser/static/styles.css:1688-1690 and comment :1673-1677; token defined at :394-400 and registered at docs/design-system.md:1893-1913 for PR numbers only; Files test pins it (tests/dom/files-tab-chrome.mjs:325, tests/test_files_tab_chrome.py:387-392). Coordinator chose option (a): --count-numeral-weight. Review A round 1 on PR #473: https://github.com/jlevy/metabrowser/pull/473#pullrequestreview-5915676394
