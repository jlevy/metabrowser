---
type: is
id: is-01m7ps02xeyq573ycx69a5zw38
title: "metab --present: which app copy takes a URL while an older one runs (#540 A9)"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7nyeb57h28trbdp2m1hy2wk
created_at: 2026-11-18T07:30:02.797Z
updated_at: 2026-11-18T07:30:02.797Z
---
Deferred from PR #540 review A9: the marker is read from the on-disk bundle, not the running app. Hand check 8 in qa-macos-app-hand-checks.md records which copy LaunchServices picks; change code only after its result.
