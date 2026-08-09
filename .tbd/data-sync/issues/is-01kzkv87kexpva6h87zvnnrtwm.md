---
type: is
id: is-01kzkv87kexpva6h87zvnnrtwm
title: "PR #22 review R12: /api/catalog does two O(N) materializations on the event loop"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01kzkv76p2eprd181arkqfj0we
created_at: 2026-08-09T18:06:09.005Z
updated_at: 2026-08-09T18:06:09.005Z
---
inventory.py:245-253 and events_route.py:658-666. Only json.dumps() runs in asyncio.to_thread(); catalog_files() walks the full inventory and allocates a list, then the route allocates the full list of wire dicts, both before the first await. At the 100k design center and 500k cap a catalog request or reconnect can stall unrelated requests and the event stream. Fix: cache a revision-keyed immutable or pre-encoded representation as inventory state changes, or build and encode a synchronized snapshot off-loop; do not traverse the live mutable dict from a worker without an explicit synchronization design.
