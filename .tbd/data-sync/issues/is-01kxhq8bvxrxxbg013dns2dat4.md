---
type: is
id: is-01kxhq8bvxrxxbg013dns2dat4
title: "PR #1 review A2: make live-tail offsets byte-correct"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01kxhq7jqryap25akmqvvxvhvr
created_at: 2026-07-15T01:46:26.556Z
updated_at: 2026-07-15T01:46:26.556Z
---
Review A2 (Medium). src/metabrowser/sse.py: byte cursors must read binary slices and decode without duplicate or garbled Unicode events.
