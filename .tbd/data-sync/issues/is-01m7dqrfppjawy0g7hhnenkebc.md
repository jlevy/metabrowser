---
type: is
id: is-01m7dqrfppjawy0g7hhnenkebc
title: "Benchmark: time from a file change to an open page"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqm6j75a103hpze839wg7j
created_at: 2026-11-14T19:15:15.285Z
updated_at: 2026-11-14T19:15:15.285Z
---
Follow-up to the baseline scale benchmark (spec: The Baseline Benchmark).

The natural evidence for live watching is the time from a file change on disk to the event reaching an open page. devtools/bench_serving.py observes a change only as a treemap ETag advance (around :1129-1139), so this needs new harness work: write a file under the served root, subscribe to the event stream, and time the delivery, reported as a distribution. Add it to make benchmark and docs/scale-benchmark.md once it is measured on the baseline machine.
