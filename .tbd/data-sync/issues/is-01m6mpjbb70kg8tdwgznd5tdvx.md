---
type: is
id: is-01m6mpjbb70kg8tdwgznd5tdvx
title: Test whether natural intent timing and request joining prepare navigation
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-21-load-time-performance.md
delegate: codex-prefetch
labels: []
dependencies: []
parent_id: is-01m6mp811vf52jmazawykb3bw6
hold: null
hold_until: null
created_at: 2026-11-05T01:53:24.838Z
updated_at: 2026-11-14T18:43:37.998Z
started_at: 2026-11-05T01:53:25.753Z
---
H75 in the load-time plan. On current main, compare 0, 100, 200 and 450 ms pointer dwell and keyboard selection for identical cold selected subjects in Pulls and Commits. Record when preparation starts, held and in-flight reuse, exact matching data-request counts, request concurrency, cancellation, and click to correct painted ready. Reject timer or coordination changes unless missed preparation or duplicate selected work is measured, and distinguish intentional conditional revalidation from overlapping duplicate reads.

H92 (exp-065) measured and fixed the join clause for the Pulls selection, and H94 (mb-fejb) carries the same sweep for files; this bead is the intent-timing sweep for PR and Git rows. Follow the performance-loop accept rule: at least three admissible runs per condition and five or more interleaved pairs for effects below 2x, with frozen corpus, cache and build identities. The original control, db52ec09 on codex/perf-prefetch-20261104, predates #299 and its merged successors. Parent mb-4ifm.

## Notes

Follow-up outside stack #302. The natural dwell and keyboard sweep is still needed before drawing a conclusion about intent timing.
