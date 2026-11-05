---
type: is
id: is-01m6mpjbb70kg8tdwgznd5tdvx
title: Test whether natural intent timing and request joining prepare navigation
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-prefetch
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T01:53:24.838Z
updated_at: 2026-11-05T18:49:23.032Z
started_at: 2026-11-05T01:53:25.753Z
---
On unchanged db52, compare 0, 100, 200 and 450 ms pointer dwell and keyboard selection for identical cold selected subjects. Record when preparation starts, held/in-flight reuse, exact matching data-request counts, request concurrency, cancellation and click-to-correct-painted-ready. Reject timer/coordination changes unless missed preparation or duplicate selected work is measured. Distinguish intentional conditional revalidation from overlapping duplicate reads. Follow the existing Web Performance Framework and performance-loop accept rule. At least three admissible runs per condition; use five or more interleaved pairs for expected effects below 2x. Preserve both installed user previews and actual frozen corpus/cache/build identities. Parent mb-4ifm; branch codex/perf-prefetch-20261104.

## Notes

Follow-up outside stack #302. The natural dwell and keyboard sweep is still needed before drawing a conclusion about intent timing.
