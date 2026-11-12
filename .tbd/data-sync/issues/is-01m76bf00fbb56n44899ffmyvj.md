---
type: is
id: is-01m76bf00fbb56n44899ffmyvj
title: "PR #341 A9: malformed path data after Z hangs the SVG renderer"
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:40.366Z
updated_at: 2026-11-12T00:14:51.861Z
started_at: 2026-11-11T22:45:10.978Z
closed_at: 2026-11-12T00:14:51.860Z
close_reason: "fixed in 68e84ae2 (A9): close-path ends repetition, forward progress enforced; rejects fixtures"
resolution: null
duplicate_of: null
---
Low. apps/macos/AppIcon/render-svg.swift:276: d="M0 0Z1" repeats Z forever without advancing. Review A9 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012.
