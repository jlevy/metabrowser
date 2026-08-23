---
type: is
id: is-01m0pxe82wj7hmdhrrszq95qkc
title: "Clicks queue behind the prefetch sweep: HTTP/1.1 has 6 slots and SSE holds 2"
kind: bug
status: open
priority: 0
version: 4
labels: []
dependencies: []
created_at: 2026-08-23T08:57:48.378Z
updated_at: 2026-08-23T18:25:51.762Z
---
ROOT CAUSE FOUND, from a visible-browser run on a 241,063-file tree. It is not the main thread and it is not the server. It is HTTP/1.1 connection starvation: a user-initiated request queues behind speculative prefetches for seconds.

THE EVIDENCE, two rows from metabrowserPerf.report() that settle it:

    /api/tree?path=scripts&depth=2     client 6,610.7 ms    server_ms 12.4
    /api/tree?path=shortcuts&depth=2   client 6,606.3 ms    server_ms 10.6

The server answered in about twelve milliseconds and the client saw six and a half seconds. That gap is queueing. Nothing in the server and nothing in script accounts for it.

WHAT IT DOES TO A CLICK:

    selectFile      n=22   max 8,896.0 ms   total 13,288.3 ms
    apiFile:json    n=9    max 8,482.3 ms   total  8,564.4 ms   threw: true

Selecting a file took 8.9 s, of which 8.5 s was its own fetch waiting for a connection, and the fetch then failed. That is precisely the reported symptom -- click a nav row, nothing happens.

THE MECHANISM. The server negotiates HTTP/1.1, where browsers allow six concurrent connections per origin. The app holds TWO of them open permanently as EventSource streams (app.js:5730 and app.js:6789), which never close. Four slots remain for every fetch the page makes, and the folder-warming sweep issues many at once -- 51 apiTreeSubtree:json calls in the run above. A click arrives, finds no free slot, and waits for a speculative request it did not ask for.

This gets worse exactly where it was reported: a bigger tree has more folders to warm, and a scan in progress produces more of them. It would be worse again over `--remote`, where every occupied slot is held for a round trip rather than for twelve milliseconds.

WHAT THIS REFUTES, and both were mine. The live-update path is not the blocker: instrumented at the batch it sums to tens of milliseconds (fileStoreApplySnapshot 17.3 ms for the whole snapshot, renderTreeNodes:root 11.5 ms max). And every long-task figure recorded before this run was taken through a hidden pane, where Chromium throttling manufactures multi-second tasks; those numbers are void. Note also that measureAsync spans wall time INCLUDING awaits, so selectFile at 8.9 s is 8.9 s of waiting, not of blocking -- a distinction worth keeping when reading these tables.

FIXES, in the order they are worth trying:

1. Bound speculative concurrency and keep a slot free. The sweep is speculative; the click is not. Today they share a budget of four with no priority between them.
2. Preempt: abort in-flight speculative fetches when a user-initiated request needs a slot. AbortController makes this cheap and it directly restores the interaction.
3. Serve HTTP/2, which multiplexes over one connection and removes the six-connection cap outright. This is the structural fix and the largest change; it also reclaims the two slots the event streams hold.
4. Reconsider two permanent EventSource connections. A third of the HTTP/1.1 budget is spent before the page fetches anything.

MEASUREMENT NOTE for the next round: server_ms comes from the Server-Timing header and is the field that separates these cases. A client duration far above server_ms is queueing; the two moving together is the server. That one comparison would have found this hours sooner than long-task counting did.
