---
type: is
id: is-01kzsrnrmbnkra45cm5wgfy6p4
title: "PR #30 review R8: avoid per-directory cancellable-thread overhead"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01kzsrn1678d07r42wx26b1kwh
created_at: 2026-08-12T01:16:33.290Z
updated_at: 2026-08-12T01:33:15.230Z
closed_at: 2026-08-12T01:33:15.229Z
close_reason: Replaced per-directory cancellable-thread wrappers with asyncio.to_thread while retaining cancellable workers for longer setup paths.
---
PR #30 senior review R8, walker.py:390. walk_tree allocates a cancellation Event, Task, and shield future for every directory scan; use asyncio.to_thread on this already-yielding hot path.
