---
type: is
id: is-01m0nw7wbymprwzy5j1x54r3b7
title: Skip tally recompute entirely while scanning (H36/S3)
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-22T23:17:36.764Z
updated_at: 2026-08-22T23:17:36.764Z
---
Review suggestion S3. The tally pass still runs in asyncio.to_thread, still GIL-bound Python competing with the walker, just less often. Cheaper step than S1: while inventory_status() reports scanning, serve the last memo regardless of age (the client is already told the numbers are provisional) and recompute once on walk completion.
