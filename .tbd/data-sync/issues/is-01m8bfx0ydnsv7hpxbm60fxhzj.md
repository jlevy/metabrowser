---
type: is
id: is-01m8bfx0ydnsv7hpxbm60fxhzj
title: Runtime conformance in process and in a worker, and a cross-interpreter CI job
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-26T08:35:08.365Z
updated_at: 2026-11-26T08:35:08.365Z
---
Phase 1 (plan: The Plugin Runtime, Testing Strategy). The runtime is bound two ways, to the server's own functions in process and to host calls in a worker, and the in-process path stays until Phase 5. One fixture plugin run both ways with matching --api transcripts holds the two bindings together. A CI job runs the worker on an interpreter that is not the host's (the design's central property), with the fixture environment built offline: a standard-library venv with a hand-written dist-info and .pth, as explorations/plugin-worker-spike/probes.py does, so no test needs a network or a build backend.
