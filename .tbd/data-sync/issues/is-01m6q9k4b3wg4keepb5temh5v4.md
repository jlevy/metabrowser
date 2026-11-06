---
type: is
id: is-01m6q9k4b3wg4keepb5temh5v4
title: Render Treemap for Git-backed folders
kind: bug
status: in_progress
priority: 2
version: 3
delegate: codex@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-06T02:04:22.238Z
updated_at: 2026-11-06T02:09:41.463Z
started_at: 2026-11-06T02:04:22.710Z
---
A completed pinned Git rollup returns index_status=complete, outside the shared rollup contract, leaving Treemap and its totals on loading placeholders. Use the shared done status, assert the full wire envelope in the CLI golden, and verify the live browser.

## Notes

Reproduced on the managed public SoftSchema repository: index metadata was done and rollup data complete, but the Git route used a status outside the shared envelope. Fixed on 11a06594 and added the contract assertion to the CLI golden. Fifty focused checks and wheel smoke passed. Restarted the local server with the new installed build and verified root and nested Treemaps. Full verification is running.
