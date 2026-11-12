---
type: is
id: is-01m76beye00mkad7yz5rapq87w
title: "PR #341 A5: failed rediscovery clears the display but keeps the rejected runtime for new folders"
kind: bug
status: in_progress
priority: 2
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76bebqayw0ze5xz60yhthtw
hold: null
hold_until: null
created_at: 2026-11-11T22:25:38.752Z
updated_at: 2026-11-12T00:03:11.838Z
started_at: 2026-11-12T00:03:11.837Z
---
Medium. apps/macos/Sources/Metabrowser/AppDelegate.swift:249: only runtimeModel.setup is cleared; AppDelegate.setup keeps the old runtime for request(). Review A5 https://github.com/jlevy/metabrowser/pull/341#pullrequestreview-5866036012.
