---
type: is
id: is-01m8bb55ne0vf762rwbv9nwfpm
title: "Files tab Chrome check: file-refresh step's written stays false under load"
kind: bug
status: closed
priority: 2
version: 5
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T07:12:12.461Z
updated_at: 2026-11-26T10:01:11.353Z
started_at: 2026-11-26T08:20:30.664Z
closed_at: 2026-11-26T10:01:11.352Z
close_reason: "Merged in #878"
resolution: null
duplicate_of: null
---
tests/test_files_tab_chrome.py::test_the_files_filter_menus_in_chrome failed its file-refresh step (written stayed false) locally at load average ~150, with main's code too; passed in CI. Find the mechanism (no 'flaky').

## Notes

PR https://github.com/jlevy/metabrowser/pull/878 (open, not merged). Mechanism: the host's FSEvents delivered no file event, so the write never reached the server's watcher or the page. Reproduced 2026-11-26 at load average ~35 with the wait raised to 45 s: watcher started mode=native and logged no batch, the page's event stream was open (readyState 1), and no grouped refresh was asked for. Outside Metabrowser, watchfiles.awatch saw no event in 30 s for files written under /private/var/folders, /private/tmp and the repository's attic, while force_polling saw each in 1 to 2 s; fseventsd had 4,654 CPU minutes over 8 days of uptime. Not load, not the refresh pacing, not the test's wait. Fix: the check counts fs.change events on the page's own stream after the write (refreshDelivered) and, when the refresh did not paint and none came, fails by that name. The page's store is not the signal: the stream carries the tree two levels deep, so it never holds src/lib/k99.py (the first push failed in CI on that). Still fails on such a host. Follow-up not filed: the product reports the watcher running while no event arrives, so the tree is not live and nothing says so.
