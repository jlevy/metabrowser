---
type: is
id: is-01m839ga4kf87q8n4p3q29rqrv
title: Check slash-branch Files pin separately from repository HEAD in live GitHub smoke
kind: bug
status: in_progress
priority: 1
version: 2
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hhr2r1bmm0ve8a6qs5nnqw
hold: null
hold_until: null
created_at: 2026-11-23T04:09:24.872Z
updated_at: 2026-11-23T04:09:45.895Z
started_at: 2026-11-23T04:09:45.875Z
---
Release 0.13.0 live GitHub smoke asserts the Files pin as the repository Commits HEAD. Verify the slashed branch through source status and the mirror default through Git repository status. Preserve repository-wide Pulls and Commits.
