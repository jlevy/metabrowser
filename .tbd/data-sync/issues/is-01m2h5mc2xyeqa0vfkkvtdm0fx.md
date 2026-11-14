---
type: is
id: is-01m2h5mc2xyeqa0vfkkvtdm0fx
title: Serving waits for watcher registration, so the socket opens late on a deep tree
kind: bug
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
labels: []
dependencies: []
parent_id: is-01m0k5wh7jgr0dgs5y78kwwke1
created_at: 2026-09-14T23:56:54.749Z
updated_at: 2026-11-14T18:45:35.896Z
---
Startup binds late on a deep tree. The lifespan (events_route.py:199-201) awaits runtime.open(root), and the Python provider's open waits for the native watcher to start (python_inventory.py:4137-4140), so uvicorn accepts nothing until watcher registration finishes: about 4 s after process start on project-10 (31,481 directories, quiet 4-CPU host, 2026-09-15). v0.9.1 bound first and did that work afterwards, so it could answer at 0.58 s; the v0.10.0 candidate never did (spawn_to_serving 3.7-3.9 s in every pair), while both had the same worst case. Measured at 03fd7997 against v0.9.1 (exp-034); re-measure on main before fixing.

Fix direction: let the lifespan yield before corpus-proportional watcher registration, so the socket accepts immediately. That changes what a client can miss between bind and watcher readiness, which is the state-and-delivery contract's subject, so it needs a written design and a deterministic test that the server answers before registration completes.

## Notes

Corrected after measuring: the serve-time KPress prewarm is NOT the cause. Timed in the candidate's own environment, importing metabrowser.server costs 435-448 ms and prepare_browser_assets 108-116 ms (0.4 ms on a second call), together about 0.55 s, not the 3.3 s the first measurement suggested.

What actually happens, from a DEBUG-level startup on project-10 (31,481 directories): the lifespan awaits runtime.open(root), which starts the native inotify watcher, and 'inventory opened' is logged about 4 s after the process starts. Uvicorn binds only after lifespan startup returns, so the socket does not accept until then. v0.9.1 binds first and does the equivalent work afterwards, so a request that arrives before the loop blocks is answered immediately.

That makes the metric bimodal for the control and stable for the candidate, on the same host, corpus and harness:

- five-pair series: control 0.559, 0.575, 0.584, 0.610, 3.973 s; candidate 3.732-3.929 s.
- two-pair series minutes later: control 3.708, 3.816 s; candidate 3.709, 3.799 s, pair ratios 1.02 and 0.97.
- a standalone reproduction of the same loop: control 3.767 s, candidate 3.746 s on project-10; control 0.574 s, candidate 1.438 s on the 300,000-file corpus, where only 1,104 directories are registered and the difference is process startup.

So the candidate's floor is higher: v0.9.1 can answer at 0.58 s and the candidate never does, while the worst case is the same for both. No pair ratio on this metric can be read as a regression without saying which mode the control was in.

Fix direction, deferred beyond v0.10.0: let the lifespan yield before corpus-proportional watcher registration so the socket accepts immediately. That changes what a client can miss between bind and watcher readiness, which is the state-and-delivery contract's subject rather than a local optimization.
