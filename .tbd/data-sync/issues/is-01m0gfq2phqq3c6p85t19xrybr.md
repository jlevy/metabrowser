---
type: is
id: is-01m0gfq2phqq3c6p85t19xrybr
title: Push aggregate deltas over SSE instead of client rollup polling
kind: feature
status: open
priority: 3
version: 5
labels:
  - deferred
dependencies: []
parent_id: is-01m0gfpa3nt74hvrnqbyqhn0ya
created_at: 2026-08-20T21:02:31.121Z
updated_at: 2026-08-20T21:18:52.979Z
---
The client refetches the whole rollup envelope on every inventory change, on a
trailing debounce bounded by one window. Entries already work the other way:
computed once, pushed over SSE, applied incrementally into client stores.

Bring aggregates onto that model -- the server publishes per-directory aggregate
deltas, and the client keeps a store it patches rather than an envelope it
replaces.

Blocked on the scope question, which is why aggregates are pulled today:
/api/events filters live fs.change to root-depth-2, so a change deep in the tree
never reaches the client. Pushing aggregates means either widening that scope
(cost: event volume on a large tree) or publishing aggregate deltas keyed by
directory, independent of entry scope (preferred -- volume is bounded by the
number of directories whose totals actually moved).

This is a change to an internal contract (/api/*, the SSE event set, and the
window.metabrowser directory-totals surface). Server, shell, and built-in
plugins ship as one artifact, so it lands in one commit across all three, with
a CHANGELOG note.

--- Re-measured after mb-l8oy and mb-weoj landed (2026-08-20) ---

Settled index, identical concurrent requests: the aggregate layer is now
effectively compute-once. 8 clients went 236ms -> 30ms wall, flat in client
count. This case is solved; push would add nothing.

During a scan the index revision moves on every write, so no body is reusable
and every poll is a real aggregation. N tabs on one folder, 100k-file tree:

  tabs   walk time   polls   poll p50
     1      15.7s      11      179ms
     4      19.0s      60       74ms
     8      25.4s     167       61ms

So the remaining cost is scan-time only and bounded: 8 tabs slow the crawl by
62%. Per-poll latency is fine and actually falls as tabs are added, because
polls land closer together and hit the shared computation more often.

RECOMMENDATION: defer. The two cheap fixes captured the steady-state win, and
what is left is a transient cost during a crawl that lasts ~17s, in exchange
for a break across three internal contracts plus an unresolved scope decision.
Revisit if scan-time multi-tab use turns out to matter, or if the walk gets
slower for other reasons.
