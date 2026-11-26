---
type: is
id: is-01m8bb55ne0vf762rwbv9nwfpm
title: "Files tab Chrome check: file-refresh step's written stays false under load"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T07:12:12.461Z
updated_at: 2026-11-26T07:12:12.461Z
---
tests/test_files_tab_chrome.py::test_the_files_filter_menus_in_chrome failed its file-refresh step (written stayed false) locally at load average ~150, with main's code too; passed in CI. Find the mechanism (no 'flaky').
