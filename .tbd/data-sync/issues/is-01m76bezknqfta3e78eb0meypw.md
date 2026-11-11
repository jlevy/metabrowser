---
type: is
id: is-01m76bezknqfta3e78eb0meypw
title: "PR #341 A8: the SVG renderer skips attribute checks on the root and filter primitives"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:39.956Z
updated_at: 2026-11-11T22:45:11.361Z
started_at: 2026-11-11T22:45:11.360Z
---
Low. apps/macos/AppIcon/render-svg.swift:367: render() never checks document.root, and filter primitives have no attribute allowlist. Review A8 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012.
