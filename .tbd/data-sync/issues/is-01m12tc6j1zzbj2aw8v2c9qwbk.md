---
type: is
id: is-01m12tc6j1zzbj2aw8v2c9qwbk
title: Replace visible loading text in the Git panel with skeleton blocks
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m12tc1tacfnggr44ecjnb17d
created_at: 2026-08-27T23:55:08.736Z
updated_at: 2026-08-28T00:11:19.442Z
closed_at: 2026-08-28T00:11:19.441Z
close_reason: "Fixed in 101b4ad: first paint, evicted-page placeholder, and next-page footer all draw skeleton rows via a repeating gradient, with the row pitch from SWIMLANE_HEIGHT through a custom property. Verified live: skeleton with no visible text and no spinner, then rows at ~400ms."
resolution: null
duplicate_of: null
---
Three visible strings, one of which is what prompted this: git-panel.js:1272 renders '<div class="loading"><div class="spinner"></div>Loading history…</div>' on first show of the Git tab; :1011 sets placeholder.textContent = 'Loading history…' for an evicted page; :1414 sets trailing.textContent = 'Loading…' for the next-page footer. All three should be skeleton rows using the shared pulse, keeping an sr-only accessible name.
