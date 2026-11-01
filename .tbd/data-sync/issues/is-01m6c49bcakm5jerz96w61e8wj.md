---
type: is
id: is-01m6c49bcakm5jerz96w61e8wj
title: A selection swap with the same file already open stays on the old pin
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T18:00:00.137Z
updated_at: 2026-11-01T18:00:00.137Z
---
Found 2026-11-01 in headless Chrome, 5 of 5. source-freshness.js near line 834 calls location.assign; when only the fragment differs that is a same-document navigation, so the page stays on the old pin while the server serves the new one, with a single /api/file fetch. The anchor lands, on the old pin's copy. Only when the reader has that file open while the selection waits. Stale text itself was not observed, because the fixture's file was identical on both branches.
