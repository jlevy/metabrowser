---
type: is
id: is-01m6n17whe9tnqh95c7j5560rr
title: Advertise retained PR DOM only for views with real cancellation
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
assignee: jlevy
delegate: jlevy
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T04:59:56.332Z
updated_at: 2026-11-05T04:59:56.847Z
started_at: 2026-11-05T04:59:56.846Z
---
The PR route mounter always returns a cancelPending wrapper, including for a custom view that implements only destructive dispose. The host uses the presence of cancelPending as its capability to retain inert old DOM. Its fallback calls destructive dispose immediately but returns a retained finalizer, falsely advertising retention and calling dispose again at later handoff. Builtin PR implements true DOM-preserving cancellation and is unaffected. Fix only the wrapper capability advertisement: expose cancelPending when the underlying view actually implements it, retain immediate disposal for pending/nonretainable views, and preserve builtin behavior. Prove source RED then GREEN using the existing exact-production focused DOM session with dispose-only and real-cancel positive controls; root independently owns builds/gates. Related feature mb-4ifm, selected-core H77.
