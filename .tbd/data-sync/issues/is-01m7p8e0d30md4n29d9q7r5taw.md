---
type: is
id: is-01m7p8e0d30md4n29d9q7r5taw
title: "macOS app: File > Open URL… that opens a pasted GitHub repository, pull request, or file URL as the web UI and metab would, and refuses any other URL with a clean message"
kind: feature
status: in_progress
priority: 1
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
hold: null
hold_until: null
created_at: 2026-11-18T02:40:33.186Z
updated_at: 2026-11-18T02:41:29.511Z
started_at: 2026-11-18T02:41:29.510Z
---
Owner, 2026-11-18 in chat: 'let's have it support an Open URL... that initially, only opens GitHub URLs and gives a clean error message if it's not a supported GitHub URL, but otherwise it should open repos, files, or PRs just like the web or CLI app would'. Builds on #539 (mb-87j0: the app opens GitHub links through metab --present, #540). Owned by the Local build review session's lane.
