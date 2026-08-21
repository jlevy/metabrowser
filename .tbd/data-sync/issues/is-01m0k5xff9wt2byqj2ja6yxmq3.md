---
type: is
id: is-01m0k5xff9wt2byqj2ja6yxmq3
title: Move /api/catalog to the on-demand tier, fetched when the finder first opens
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-08-21T22:08:58.345Z
updated_at: 2026-08-21T22:48:27.648Z
---
Deferring the first /api/catalog fetch until the Quick File finder opens takes 4,580,060 bytes (at 100k files) off the load path.

Not a moved call. catalog_feed.js buffers catalog.change deltas into pendingChanges whenever !fetchedOnce, and that array is unbounded and only drains when the bulk payload lands. Deferring the first fetch indefinitely grows it for the life of the session. The fix needs a buffering policy: either do not subscribe until started, or bound the buffer and treat overflow as the resync the module already handles.

The module already supports a late first start: its start() path for 'later opens refetch to cover deltas lost while disconnected' is the same code path, and the bulk payload is authoritative as of fetch. Called today from the EventSource onopen handler in app.js (~line 6515) and from startInventoryEventStream's no-EventSource fallback.
