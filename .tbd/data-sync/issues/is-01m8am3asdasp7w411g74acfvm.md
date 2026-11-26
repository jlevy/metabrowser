---
type: is
id: is-01m8am3asdasp7w411g74acfvm
title: "Files filter menus Chrome check: a file written into src/lib never shows in the tree within 15 s on this machine"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T00:29:14.924Z
updated_at: 2026-11-26T00:29:14.924Z
---
tests/test_files_tab_chrome.py::test_the_files_filter_menus_in_chrome fails locally on main at 90a732498 and on PR #857's branch (refresh.after.written stays false). PR CI skips it (--skip-slow); main's full tier runs it. Suspected mechanism, unconfirmed: macOS FSEvents delivery lag under very high load (load average 100-400). Find the mechanism: compare the watcher path on macOS vs Linux, measure event latency under load, and check the test's wait against the watcher's debounce.
