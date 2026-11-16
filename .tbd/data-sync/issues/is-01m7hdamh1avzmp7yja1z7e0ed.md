---
type: is
id: is-01m7hdamh1avzmp7yja1z7e0ed
title: "PR #457 A3: the app-menu check misses an uppercase key equivalent or a multi-line menu item"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7hcje01mnwqrrmfa3d3b88g
hold: null
hold_until: null
created_at: 2026-11-16T05:29:53.439Z
updated_at: 2026-11-16T06:13:16.907Z
started_at: 2026-11-16T05:30:01.509Z
closed_at: 2026-11-16T06:13:16.906Z
close_reason: "fixed in 1f556e6: menu check holds every modifier mask to MainMenu.item and reads key-modifier pairs whitespace-free and case-insensitively. Disposition: https://github.com/jlevy/metabrowser/pull/457#issuecomment-6908902070"
resolution: null
duplicate_of: null
---
Low. PR #457 review A (https://github.com/jlevy/metabrowser/pull/457#pullrequestreview-5915398035). tests/test_modified_keys.py:351-362; apps/macos/README.md:995-998; MainMenu.swift:95-99.
