---
type: is
id: is-01m7dqrc33kxhve8xyrs14eqv3
title: "Architecture: CLI, server, inventory provider, Python engine, live delivery"
kind: task
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmdjvjrgqd3vpqw3z3zdc
created_at: 2026-11-14T19:15:11.586Z
updated_at: 2026-11-15T05:56:38.985Z
---
Phase 2, PR 1: CLI, server, inventory, and delivery (spec: Architecture Documents).

- New arch-cli.md (about 200 lines): modes, the serve lifecycle, in-process --api dispatch, remote tunnels, and process exit (including the --exit-on-eof handling that phase 1 moved to a docstring).
- New arch-inventory-engine-python.md (about 200): the only engine-specific document: walker, concurrency, the watcher backend (watchfiles, native or 2 s polling, watch_backends.py:186-205; batching and the default filter are undocumented today), and unit costs. Sources: arch-python-inventory-cost.md, arch-state-and-delivery.md :168-206, arch-inventory-provider.md :130-146 and :408-416.
- Make arch-inventory-provider.md engine-independent: remove Python retained state (:106-107, :130, :139-146, :347, :408-416) and the present-tense fdu mapping (:295-307, :416). Copy, do not delete, its engine-independent rule from docs/engine-performance-model.md :35-70 (the contributor PR owns that file).
- New arch-live-delivery.md (about 300): from the provider's change feed to browser stores: events, recovery, invariants. It states only what the provider guarantees.
- Complete arch-server-and-content.md: request flow, safe paths, validators (copy from docs/architecture.md :7-78 and arch-state-and-delivery.md :325-404).
- Retire arch-state-and-delivery.md and arch-python-inventory-cost.md. Trim docs/realtime-debugging.md.
- No benchmark figures restated; link docs/scale-benchmark.md.

Known errors to fix (verified at c098e6a8):
- arch-state-and-delivery lists file.* events that nothing constructs (tests only); tailing uses /api/stream (sse.py:15-24). :576 misdescribes the catalog (static/catalog-feed.js:3-6).
- It says cancellation reaches every waiter (:318-320); server.py:347-351 shields the build, and its own :792 says the opposite.
- It says fileStore is dropped (:620); app.js:7822 keeps it.
- docs/realtime-debugging.md:8 versus server.py:1109-1118.
- settings.py:100-105 records a Python walk rate beside the cap; it belongs in the engine document.
