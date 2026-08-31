---
type: is
id: is-01m1apk5p5n60vk5xhgspxx098
title: "PR #90 P90-12: Boundary regex denylist has gaps"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m1apk016z6h7ms919ekta9z0
created_at: 2026-08-31T01:22:58.373Z
updated_at: 2026-08-31T01:40:12.969Z
closed_at: 2026-08-31T01:40:12.969Z
close_reason: "Fixed on feat/cli-parity-mechanism; see the disposition map on PR #90."
resolution: null
duplicate_of: null
---
The lookahead excludes only word characters, dot and dash, so /tmp/sb+extra normalizes to <ROOT>+extra.
