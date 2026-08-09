---
type: is
id: is-01kzksyp6t89mxx81ryqjbdbs7
title: "PR #22 review R4: stale bulk fetch applies after resync (catalog_feed.js)"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzksyn1g7gqhyw86ssr1gfvt
created_at: 2026-08-09T17:43:27.704Z
updated_at: 2026-08-09T17:49:46.671Z
closed_at: 2026-08-09T17:49:46.669Z
close_reason: "Fixed in 9b6baea: requestRefetch invalidates in-flight serial and queues follow-up; repro test verified failing on prior code."
---
Bugbot 3742621180, High. Real: onResync calls runFetch which returns while fetching=true, so no refetch is queued AND the in-flight response keeps a current serial and applies pre-resync data to a just-cleared catalog. Fix: requestRefetch() that bumps fetchSerial (invalidating in-flight) and queues a follow-up fetch from the finally block.
