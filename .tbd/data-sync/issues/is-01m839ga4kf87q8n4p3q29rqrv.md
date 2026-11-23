---
type: is
id: is-01m839ga4kf87q8n4p3q29rqrv
title: Check slash-branch Files pin separately from repository HEAD in live GitHub smoke
kind: bug
status: in_progress
priority: 1
version: 6
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/730
    at: 2026-11-23T04:15:29.917Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/45110634146
    at: 2026-11-23T04:27:38.880Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hhr2r1bmm0ve8a6qs5nnqw
hold: null
hold_until: null
created_at: 2026-11-23T04:09:24.872Z
updated_at: 2026-11-23T04:27:38.888Z
started_at: 2026-11-23T04:09:45.875Z
---
Release 0.13.0 live GitHub smoke asserts the Files pin as the repository Commits HEAD. Verify the slashed branch through source status and the mirror default through Git repository status. Preserve repository-wide Pulls and Commits.

## Notes

Test-only PR #730 exact head d4bc81419. No production changes. Targeted real GitHub slash-branch test passed in 42.15s. Normal pre-commit and exact hosted CI passed. Both real GitHub opt-in modules passed all eight tests at exact head in 352.93s.
