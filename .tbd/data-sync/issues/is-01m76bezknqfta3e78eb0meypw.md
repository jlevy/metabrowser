---
type: is
id: is-01m76bezknqfta3e78eb0meypw
title: "PR #341 A8: the SVG renderer skips attribute checks on the root and filter primitives"
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
created_at: 2026-11-11T22:25:39.956Z
updated_at: 2026-11-12T00:14:51.496Z
started_at: 2026-11-11T22:45:11.360Z
closed_at: 2026-11-12T00:14:51.495Z
close_reason: "fixed in 68e84ae2 (A8): root, filter primitive, and stop attributes checked; AppIcon/rejects fixtures checked by build-icon.sh"
resolution: null
duplicate_of: null
---
Low. apps/macos/AppIcon/render-svg.swift:367: render() never checks document.root, and filter primitives have no attribute allowlist. Review A8 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012.
