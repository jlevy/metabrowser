---
type: is
id: is-01m6mpjbqxs81cdgeg8fgjgjat
title: Measure the prepared navigation render floor before adding more prefetch
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-prefetch
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T01:53:25.244Z
updated_at: 2026-11-05T03:19:52.850Z
started_at: 2026-11-05T01:53:25.760Z
---
On unchanged db52, separate genuinely retained payload, matching in-flight preparation and browser HTTP-cache response paths with the same subjects/assets. Determine whether decoding, schema validation, mounting or paint dominates after server/transfer time disappears. Record bytes, long tasks, DOM/retained heap and exact correctness so further network preparation is not credited for work it cannot remove. Follow the existing Web Performance Framework and performance-loop accept rule. At least three admissible runs per condition; use five or more interleaved pairs for expected effects below 2x. Preserve both installed user previews and actual frozen corpus/cache/build identities. Parent mb-4ifm; branch codex/perf-prefetch-20261104.

## Notes

Focused unchanged PR298 Files diagnostics: immediate firsttext57.3ms/viewport74.5ms; held firsttext68.3ms/viewport87ms; both no errors/blank frames/LongTasks. Held case consumed completed-and-decoded prefetch with zero new logical comparison fetches. These are setup/mechanism diagnostics, not repeated A/B speed claims. Further aggressive Files prefetch lacks evidence. Git differs: same55-file comparison carries50initialpatchmodels vsPRvisibleprefix, so no cross-path causalclaim; H79 tests identical payloads connected/detached.
