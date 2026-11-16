---
type: is
id: is-01m7hef34q8gwq6pre2pmmnp5j
title: "PR #459 A2: the Files Chrome check sleeps for a rebuild that has already happened"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcjfyhee19b9jnbk7nvqfk
hold: null
hold_until: null
created_at: 2026-11-16T05:49:48.054Z
updated_at: 2026-11-16T05:51:14.163Z
started_at: 2026-11-16T05:49:55.247Z
closed_at: 2026-11-16T05:51:14.162Z
close_reason: "Fixed in adacd3019 (first option): both sleeps dropped, MutationObserver rebuild count waited on; a file write does not rebuild the bar with a menu open. tests/test_files_tab_chrome.py passes."
resolution: null
duplicate_of: null
---
Low. tests/dom/files-tab-chrome.mjs:548-557 slept 800 ms after each Enter on a File type row; the comment there and in tests/test_files_tab_chrome.py:314-315 described a tally rebuild the check never reaches. PR #459, review A: https://github.com/jlevy/metabrowser/pull/459#pullrequestreview-5915454708
