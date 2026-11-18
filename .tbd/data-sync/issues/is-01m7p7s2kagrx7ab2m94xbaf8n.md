---
type: is
id: is-01m7p7s2kagrx7ab2m94xbaf8n
title: Golden for a pull-route inert-render refusal (#527 A7)
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m75fzpspek15x7d5dqhnc2yw
created_at: 2026-11-18T02:29:07.305Z
updated_at: 2026-11-18T02:29:07.305Z
---
Deferred from PR #527 A7: needs a deterministically slow text in tests/github_pull_fixture.py, shared by every pull golden; a 1 ms deadline on ordinary text is timing-dependent.
