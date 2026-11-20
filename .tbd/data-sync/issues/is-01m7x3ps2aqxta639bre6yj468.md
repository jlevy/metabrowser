---
type: is
id: is-01m7x3ps2aqxta639bre6yj468
title: "macOS title folder menu: the check mark of the current entry sits on the name's (first, bold) line, not centred across the two-line row, keeping the accessible checked state"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-20T18:32:38.727Z
updated_at: 2026-11-20T18:33:17.492Z
started_at: 2026-11-20T18:33:17.490Z
---
Owner 2026-11-20. Follow-up to mb-z822 (#628), which moved the cloud/folder icon to the name's line but kept the native check centred because a custom onStateImage loses AXMenuItemMarkChar (the accessible checked state). Find a way that puts the check on the first line and keeps the item reported as checked to accessibility (VoiceOver), with a test.
