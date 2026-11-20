---
type: is
id: is-01m7n6v99j0bz3n0ja7mszthq9
title: "Diff summaries: prefetch eagerly and answer from the last persisted cache file first"
kind: task
status: closed
priority: 1
version: 7
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/532
    at: 2026-11-20T17:01:09.449Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/536
    at: 2026-11-20T17:01:09.450Z
labels:
  - linear
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-17T16:53:36.689Z
updated_at: 2026-11-20T17:59:57.041Z
closed_at: 2026-11-18T17:44:10.315Z
close_reason: "Merged in #536 (stack merge 86e083f35)."
resolution: null
duplicate_of: null
extensions:
  linear:
    id: 9a22b5eb-7b45-451f-8404-e60cf0bf3f92
    linked_at: 2026-11-20T17:59:57.039Z
---
Prefetch diff summaries for the pull requests visible in the Pulls nav and the selected one, persist them as files in the repository cache (home.py / cache helpers, the GitHub plugin's refresh machinery), and answer from the last persisted version first with refreshes layered on top, so rows and the PR page show a current or recent value at once. CLI parity: any new route or persisted state gets a metab equivalent and golden.

## Notes

Prefetch half landed in #522 (f55ab001e): the lane lists open PRs' changed files from the store first, one head fetch per ask, files before records. PR-page half (draw the cached brief line first) is #536, stacked on #532, owned by the summary-loading-box-2 session; close when #536 merges.
