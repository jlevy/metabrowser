---
type: is
id: is-01m39rqr906c0gybdkt7hmnk76
title: Load more notice keeps the original loaded size after appending text
kind: bug
status: open
priority: 3
version: 1
labels:
  - release:v0.12.0
dependencies: []
created_at: 2026-09-24T13:12:34.847Z
updated_at: 2026-09-24T13:12:34.847Z
---
From the step 8 verification (2026-09-24): after Load more on a 15 MB text file, the notice still reads 'Showing 2.0 MB of 15.2 MB' although about 4 MB is loaded. loadMoreCurrentText (static/app.js ~5108) already calls syncTruncationWarning and syncLoadMoreFooter with the updated cache value, so the stale figure comes from another path. Investigate, fix, and add a browserless test.
