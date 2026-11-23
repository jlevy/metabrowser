---
type: is
id: is-01m82x8q4mc9knbng9q51tpan4
title: Show GitHub pull requests automatically for local checkouts opened from File
kind: bug
status: in_progress
priority: 0
version: 4
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/720
    at: 2026-11-23T00:59:22.630Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-23T00:35:33.136Z
updated_at: 2026-11-23T01:05:07.567Z
started_at: 2026-11-23T00:40:54.998Z
---
The Mac File menu opens an existing local Git checkout and recognizes it as Git, yet the PR catalog is absent. Diagnose the actual Mac open path and GitHub remote/auth detection, preserve local checkout behavior, and make eligible local GitHub repositories expose and load their PR catalog automatically. Verify with a controlled remote fixture and the affected local checkout without sharing private repo data.

## Notes

Independently reviewed #720. Reproduced missing Pulls at a local checkout pin, verified the live development restart at 90e03a053, and confirmed the affected checkout’s catalog automatically refreshed to current. Separately verified the same real catalog rows are readable in an isolated pinned session without mutating the active view. Pending hosted merge gates.
