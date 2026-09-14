---
type: is
id: is-01m2etjv7bzrqm070ksxerceyn
title: Report an unreachable server as a connection problem, not a file error
kind: bug
status: closed
priority: 2
version: 3
labels:
  - ux
  - resilience
dependencies:
  - type: blocks
    target: is-01m2f0dryv9qmyp9y6g1sc4gwq
created_at: 2026-09-14T02:05:21.514Z
updated_at: 2026-09-14T03:47:26.810Z
closed_at: 2026-09-14T03:19:57.199Z
close_reason: "Fixed in PR #113: unreachable server reports a connection message and retries on event-stream reconnect."
resolution: null
duplicate_of: null
---
Report an unreachable Metabrowser server as a connection problem, not as "Could not open this file. Failed to fetch".

Observed: with the server stopped, an open tab that selects a folder or file shows "Could not open this file." with the raw fetch error "Failed to fetch". That reads as a problem with the file, and the empty folder the reader clicked looked broken, although the same folder renders correctly on a running server.

Sources: src/metabrowser/static/app.js ~5158 (the selection error falls back to the "Could not open this file." summary with the network error as detail) and ~5296; search-palette.js ~550 and ~587 use the same wording for Quick File.

Expected:
1. Distinguish network failures (fetch rejects, server gone, connection refused) from HTTP error responses. Network failures show one clear connection state, for example "Metabrowser isn't reachable. It may have stopped; start it again with `metab <folder>`, and this page will reconnect." File errors keep their current wording for real 4xx/5xx.
2. When the server returns (the event stream already reconnects with backoff), the pane retries the current selection automatically instead of staying on the error.
3. Quick File uses the same distinction.

Acceptance: browserless session plus golden covering network failure versus HTTP error presentation and recovery on reconnect; CHANGELOG entry.
