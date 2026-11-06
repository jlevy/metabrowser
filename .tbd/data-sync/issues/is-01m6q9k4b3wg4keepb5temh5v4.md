---
type: is
id: is-01m6q9k4b3wg4keepb5temh5v4
title: Render Treemap for Git-backed folders
kind: bug
status: closed
priority: 2
version: 5
delegate: codex@spud10
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-06T02:04:22.238Z
updated_at: 2026-11-06T03:01:07.864Z
started_at: 2026-11-06T02:04:22.710Z
closed_at: 2026-11-06T03:01:07.863Z
close_reason: "Fixed on the live server and in PR #306. Full local verification and all nine GitHub CI jobs passed."
resolution: null
duplicate_of: null
---
A completed pinned Git rollup returns index_status=complete, outside the shared rollup contract, leaving Treemap and its totals on loading placeholders. Use the shared done status, assert the full wire envelope in the CLI golden, and verify the live browser.

## Notes

Reproduced on the managed public SoftSchema repository: index metadata was done and rollup data complete, but the Git route used a status outside the shared envelope. Fixed on 11a06594 and added the contract assertion to the CLI golden. Fifty focused checks and wheel smoke passed. Restarted the local server with the new installed build and verified root and nested Treemaps. Full verification is running.

Published as PR #306 above #305 in native stack #302. Head 11a06594 passed make verify (4,855 tests, 381 CLI transcript checks), the pre-push gate, and all nine CI jobs in run 42152582832. Automated review found no issues. Installed build 0.11.1.dev1173+11a06594 is serving the repaired root and nested Treemaps on port 8411.
