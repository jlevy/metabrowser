---
type: is
id: is-01kxhq8czmcp0h2zpmtm8bdgy9
title: "PR #1 review A7a: move plugin classification I/O off event loop"
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:27.699Z
updated_at: 2026-07-15T01:46:27.699Z
---
Review A7a (Low). src/metabrowser/server.py/classify.py: avoid synchronous plugin classification file reads on async request paths.
