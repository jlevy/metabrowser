---
type: is
id: is-01m82vevne80te52qrwq48djn2
title: Files tab Chrome check misses a written file's refresh under heavy load
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m82hy6zdk5e5zzmsan8xhw6q
created_at: 2026-11-23T00:03:57.229Z
updated_at: 2026-11-23T00:03:57.229Z
---
tests/test_files_tab_chrome.py::test_the_files_filter_menus_in_chrome failed at 'a file written into src/lib, open inside Code's src, refreshes the sections in place' (written stays False after the session's 15 s wait, files-tab-chrome.mjs ~1001) on 2026-11-22 at load averages 260-360, on both claude/nav-hidden-centered-column (#711) and claude/wide-width-gutters (#714). Those branches change CSS and tests only, so the cause is upstream of them. Not yet shown: whether the watch event, the summary refresh, or the section re-render is what takes longer than 15 s under load. Reproduce at high load, log the watch event's and the refresh request's times, and fix the mechanism (or the bound, with the measurement beside it).
