---
type: is
id: is-01m82xjneh37qftd9yv3w30xj7
title: Keep the Pulls and Commits tabs scoped to the owning repository
kind: bug
status: closed
priority: 1
version: 5
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/720
    at: 2026-11-23T00:59:24.776Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:40:59.086Z
updated_at: 2026-11-23T01:17:00.468Z
started_at: 2026-11-23T00:42:49.860Z
closed_at: 2026-11-23T01:17:00.468Z
close_reason: "Independently reviewed and merged in #720 at 88957d954. Existing checkout repository Commits behavior and new pinned Pulls both verified. The active development app refreshed the actual repository catalog, and an isolated pinned read returned the same catalog without changing the checkout or active view."
resolution: null
duplicate_of: null
---
Treat Pulls and Commits as repository-scoped navigation on the working tree and on pinned branches, tags or commits, including views of subdirectories where supported. Browsing a file or revision should not implicitly narrow or disable the repository tabs. Preserve explicit filters and the pinned Files view.

## Notes

Live Commits reported the actual repository working-tree HEAD while Files was pinned and returned all-ref history. Existing branch, tag, remote and commit history tests passed. #720 now keeps the same PR catalog available under local checkout pins. The refreshed catalog was verified on the active checkout and in an isolated pinned session. Pending hosted merge gates.
