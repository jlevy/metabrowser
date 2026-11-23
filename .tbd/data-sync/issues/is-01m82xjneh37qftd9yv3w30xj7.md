---
type: is
id: is-01m82xjneh37qftd9yv3w30xj7
title: Keep the Pulls and Commits tabs scoped to the owning repository
kind: bug
status: in_progress
priority: 1
version: 3
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
updated_at: 2026-11-23T00:59:24.779Z
started_at: 2026-11-23T00:42:49.860Z
---
Treat Pulls and Commits as repository-scoped navigation on the working tree and on pinned branches, tags or commits, including views of subdirectories where supported. Browsing a file or revision should not implicitly narrow or disable the repository tabs. Preserve explicit filters and the pinned Files view.
