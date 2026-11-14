---
type: is
id: is-01m7bjen8x7x00nvtp8qzdvv08
title: "Commits tab starved during a large repository's first scan: a storm of slow /api/tree?depth=0 requests"
kind: bug
status: in_progress
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-11-13T23:04:01.563Z
updated_at: 2026-11-13T23:04:54.245Z
---
The user (2026-11-13): "the commits tab on the currently running native app is not loading ... this is for the trading repo window." The window serves a large private repository: about 12,800 tracked files, 248,000 ignored files (10 GB), 10,044 commits, and a 261 KB refs list.

Measured from that window's server log after a relaunch (build 3033): during the first file scan, the page requested `GET /api/tree?depth=0` 176 times in about 5 minutes, usually 4 identical requests at once every 2 s, each taking 4 to 7 s. Earlier sessions in the same log show 1,453 such slow requests. Once the scan finished, the same request took 4 ms, and `/api/git/repo`, `/api/git/refs` and `/api/git/log?limit=50` answered in 0.09 to 0.47 s; in a Chromium tab opened afterwards, Commits loaded 10,044 commits.

Likely mechanism (to confirm in the app): the storm holds most of WebKit's per-host connections (six for HTTP/1.1), alongside the event stream, so the Commits tab's requests queue behind 4 to 7 s tree requests, and the tab shows nothing or gives up. `scheduleRootSummaryRefresh` in `static/app.js` clears its debounce handle when the timer fires, before its fetch settles, so overlapping fetches stack up; other callers (`startIndexProgressPolling`, the folder overview) may add more.

Done when: reproduced in WKWebView against a large tree during its first scan; the page keeps at most one tree-summary request in flight (coalesced, with backoff while scanning); `/api/tree?depth=0` is fast while scanning, or its cost is measured and bounded; the Commits tab loads promptly during a scan and shows progress until it does; sessions and goldens pin it.
