---
type: is
id: is-01m7be81x72znwts9555x0m0rd
title: "Pulls: unlimited closed and all lists, fetched incrementally like Commits, with progress instead of count notices"
kind: feature
status: closed
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-11-13T21:50:30.822Z
updated_at: 2026-11-13T22:56:37.627Z
closed_at: 2026-11-13T22:56:37.626Z
close_reason: "Merged in #410: Pulls lists page without a total cap like Commits; Showing last N, Fetch more, and the paused-catalog text are gone; the foot reuses the file-scan progress indicator; background backfill respects the GitHub budget floor."
resolution: null
duplicate_of: null
---
The user (2026-11-13): "PRs are only showing last 500 or 600 closed PRs. can we raise this to unlimited but make sure it fetches in a sane way incrementally, much like we already do for commits" and "drop notices about only having fetched certain numbers. we can have progress indicators".

On main: `pull_catalog.py` has PAGE_SIZE 100 and MAX_WINDOW 1000 (a per-request window), and `pulls-panel.js:407` writes "Showing last N". The fetch bound behind the 500-600 closed limit is still to be found (likely in `pull_list_refresh.py` or `gh_lists.py`).

Done when: the Pulls list has no total cap; closed (and all) pull requests are fetched incrementally from GitHub in bounded pages, newest first, with rate-limit care, and the list loads further pages as the reader scrolls, as Commits does; no "Showing last N" or "only fetched N" notice remains; progress shows while pages load; sessions, goldens and docs pin it.
