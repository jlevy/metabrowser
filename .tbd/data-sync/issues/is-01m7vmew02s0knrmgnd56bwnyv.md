---
type: is
id: is-01m7vmew02s0knrmgnd56bwnyv
title: "PR #617 C5: DELETE /api/events/watch cannot be reached through metab --api"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@vm
labels: []
dependencies: []
parent_id: is-01m7vme8z9g4zntjqcdkt3y0pe
hold: null
hold_until: null
created_at: 2026-11-20T04:46:56.514Z
updated_at: 2026-11-20T05:15:05.058Z
started_at: 2026-11-20T04:47:07.172Z
closed_at: 2026-11-20T05:15:05.058Z
close_reason: "fixed: 12cc8813d unregisters with watch:false on the POST route, with goldens for both. Disposition reply: https://github.com/jlevy/metabrowser/pull/617#issuecomment-7031127972"
resolution: null
duplicate_of: null
---
docs/project/specs/active/plan-2026-11-19-tabular-data-and-live-sqlite.md:452-455,467-469; src/metabrowser/cli/api_cli.py:123-126. Unregister with a POST and give it a golden. Severity: Medium. PR #617, review C: https://github.com/jlevy/metabrowser/pull/617#pullrequestreview-5987608762
