---
type: is
id: is-01m8bjbzekfa7rxyv7z7gj6pcg
title: "Live updates: fall back to polling when FSEvents delivers nothing"
kind: bug
status: in_progress
priority: 1
version: 3
delegate: codex@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-26T09:18:15.495Z
updated_at: 2026-11-28T18:13:11.091Z
started_at: 2026-11-28T18:12:47.186Z
---
Found under mb-em6e (#878): on the owner's Mac FSEvents delivers no file events (watchfiles.awatch saw none in 30 s; polling saw writes in 1-2 s; fseventsd at 4,654 CPU minutes over 8 days), so metab's watcher reports running in native mode while no live update ever arrives. Detect a native watcher that delivers nothing (e.g. a canary write it never sees) and fall back to polling, and surface it in metab's status.

## Notes

A fresh raw watcher control after the app restart reproduced the external APFS problem on a disposable directory. Native delivery reported no event in four seconds. Polling with a 500 ms interval reported the same normal file creation in 0.484 s. Existing architecture should account for a stalled native watch on roots the app never writes to.
