---
type: is
id: is-01m39rqr906c0gybdkt7hmnk76
title: Load more notice keeps the original loaded size after appending text
kind: bug
status: closed
priority: 3
version: 3
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
hold: null
hold_until: null
created_at: 2026-09-24T13:12:34.847Z
updated_at: 2026-09-24T19:14:19.573Z
started_at: 2026-09-24T18:04:55.714Z
closed_at: 2026-09-24T19:14:19.570Z
close_reason: "Fixed in PR #237 (28ac54b3): the root cause was the server. A pin's later text window reported bytes_read as the window length rather than the position after it, which froze the notice and repeated text on the next Load more. Now matches served folders; browserless session test against a real pin."
resolution: null
duplicate_of: null
---
From the step 8 verification (2026-09-24): after Load more on a 15 MB text file, the notice still reads 'Showing 2.0 MB of 15.2 MB' although about 4 MB is loaded. loadMoreCurrentText (static/app.js ~5108) already calls syncTruncationWarning and syncLoadMoreFooter with the updated cache value, so the stale figure comes from another path. Investigate, fix, and add a browserless test.
