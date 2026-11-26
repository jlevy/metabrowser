---
type: is
id: is-01m8b811da43ghay4k4awnjzv3
title: Changes tab file filter (e.g. Documentation) no longer filters the diff
kind: bug
status: in_progress
priority: 0
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T06:17:31.305Z
updated_at: 2026-11-26T07:07:43.702Z
started_at: 2026-11-26T06:17:32.696Z
---
Owner 2026-11-26: on a diff, selecting a file-type subfilter such as Documentation does not filter. Serious regression; find which change broke it and why (bisect), fix it with a test that fails without the fix, and record the cause.

## Notes

2026-11-25 (agent). Cause found, fix in PR #873 (https://github.com/jlevy/metabrowser/pull/873), not merged.

Reproduction: WebKit only (the macOS app, Safari). In a WKWebView, a press on a row of a diff's File type menu left the diff with every file; headless Chrome filters correctly, on main and on #870's branch alike, on a pull request's Changes and a stack's.

Breaking commit: 69a4fdb98 "Close every menu alike through one helper" (PR #835, merged 2026-11-25), first bad by git bisect with a scripted WKWebView press between 40b4a6609 and main.

Mechanism: WebKit focuses no button on a press; it gives focus to the nearest ancestor a press can focus, here #preview-pane (tabindex="-1"). static/menus.js closes a menu when focus arrives outside it, so the menu closed between pointerdown and click, the control was redrawn closed, and the click never reached the row.

Why tests missed it: tests/dom/menu-dismissal-session.js modelled WebKit's press as leaving focus alone; tests/test_menu_dismissal_chrome.py presses in Chrome, which focuses the button itself; nothing presses a menu in WebKit.

Second defect, same PR #835 (77bcfbd6e), every browser: the diff's Markdown layer binds the whole diff, found the File type menu drawn open, and opened it through its own holder, which closed it at each mount, so a multi-select menu closed after every choice.

Fix: static/menus.js only. Focus that arrives while a press that went down in a menu awaits its click closes nothing; a menu another holder has open, by its trigger, is left to that holder. Session steps and golden (cli-ui-menu-dismissal) fail without each.

Open: no automated check presses a menu in the app's web view. Locally, tests/test_files_tab_chrome.py::test_the_files_filter_menus_in_chrome failed its file-refresh step at a load average near 150, with and without the change; mechanism not investigated.
