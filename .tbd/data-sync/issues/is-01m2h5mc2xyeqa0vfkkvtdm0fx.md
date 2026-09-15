---
type: is
id: is-01m2h5mc2xyeqa0vfkkvtdm0fx
title: Serving waits for watcher registration, so the socket opens late on a deep tree
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
created_at: 2026-09-14T23:56:54.749Z
updated_at: 2026-09-15T00:04:50.337Z
---
devtools.compare_builds on the repository-shaped project-10 corpus (118,860 walker-visible files), quiet 4-CPU host, v0.9.1 wheel against main 03fd7997, five interleaved pairs: candidate spawn_to_serving 3.805-3.929 s against control 0.559-0.610 s, a pair ratio of about 6.5x, repeatable in every pair. spawn_to_serving is one of the metrics the v0.10.0 release comparison judges at 1.3x per pair, so this blocks the release as measured.

Cause: cli/serve.py calls kpress_adapter.prepare_browser_assets() before find_available_local_port and uvicorn.run, so the KPress renderer import and asset resolution run before the socket answers anything. The comment records the reason -- a render-blocking request must not own the deferred KPress import while the initial walk competes for the CPU -- but the prewarm does not have to block serving to achieve that.

On the 300,000-file synthetic corpus the same metric was 1.03x and 2.40x in the two recon pairs, so the effect is not purely corpus-independent and needs measuring on both.

Fix direction: start the prewarm without holding the bind, so the socket answers immediately and the import overlaps startup. Keep the guarantee that a first render request never pays the import alone. Needs a deterministic test that the server answers before the prewarm completes.

## Notes

Corrected after measuring: the serve-time KPress prewarm is NOT the cause. Timed in the candidate's own environment, importing metabrowser.server costs 435-448 ms and prepare_browser_assets 108-116 ms (0.4 ms on a second call), together about 0.55 s, not the 3.3 s the first measurement suggested.

What actually happens, from a DEBUG-level startup on project-10 (31,481 directories): the lifespan awaits runtime.open(root), which starts the native inotify watcher, and 'inventory opened' is logged about 4 s after the process starts. Uvicorn binds only after lifespan startup returns, so the socket does not accept until then. v0.9.1 binds first and does the equivalent work afterwards, so a request that arrives before the loop blocks is answered immediately.

That makes the metric bimodal for the control and stable for the candidate, on the same host, corpus and harness:

- five-pair series: control 0.559, 0.575, 0.584, 0.610, 3.973 s; candidate 3.732-3.929 s.
- two-pair series minutes later: control 3.708, 3.816 s; candidate 3.709, 3.799 s, pair ratios 1.02 and 0.97.
- a standalone reproduction of the same loop: control 3.767 s, candidate 3.746 s on project-10; control 0.574 s, candidate 1.438 s on the 300,000-file corpus, where only 1,104 directories are registered and the difference is process startup.

So the candidate's floor is higher: v0.9.1 can answer at 0.58 s and the candidate never does, while the worst case is the same for both. No pair ratio on this metric can be read as a regression without saying which mode the control was in.

Fix direction, deferred beyond v0.10.0: let the lifespan yield before corpus-proportional watcher registration so the socket accepts immediately. That changes what a client can miss between bind and watcher readiness, which is the state-and-delivery contract's subject rather than a local optimization.
