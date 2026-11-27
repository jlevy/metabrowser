---
type: is
id: is-01m8d8j2d2f12rya3xwqfq5tsp
title: Trace visible PR core sampling across identical viewport repaints
kind: task
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
created_at: 2026-11-27T01:05:18.239Z
updated_at: 2026-11-27T01:05:18.239Z
---
Trace whether repainting the same viewport and catalog cohort restarts the 60 ms visible-core sampling deadline in pulls-panel.js enough to miss the first selected PR. Stop if the exact PR is already sampled promptly or provider admission was busy or held. If repeated rearming is causal, preserve the first sampling deadline across identical repaints. Keep scroll, filter, catalog and disposal invalidation, viewer and revision checks, the visible batch cap and foreground preemption. Run short and longer fixed-dwell Chrome inputs against the same loopback scenario with the full refresh starting at click. Require more pre-input exact-core hits and earlier matching HTML with no extra batches or regression in blank frames or full settlement. Exp-052 measured 0.41–0.56 s slower full settlement in immediate/in-flight pairs. Exp-124 proves prepared API content and cost only.
