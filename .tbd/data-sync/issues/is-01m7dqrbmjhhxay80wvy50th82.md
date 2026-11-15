---
type: is
id: is-01m7dqrbmjhhxay80wvy50th82
title: "Baseline scale benchmark: make benchmark and docs/scale-benchmark.md"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7dqrfppjawy0g7hhnenkebc
parent_id: is-01m7dqmd3wafkq2x9r1y2gt57v
created_at: 2026-11-14T19:15:11.122Z
updated_at: 2026-11-15T05:56:38.591Z
---
Phase 1, PR 8 (spec: The Baseline Benchmark).

- `make benchmark`: runs devtools/bench_serving.py on its deterministic synthetic corpus (build_corpus) at 100,000 and 300,000 files, default Python provider, one run each, and prints a Markdown table of: time from start to the first folder counts, wall time of the scan with a client attached, and peak server memory. The corpus lives under .bench/ (gitignored).
- New docs/scale-benchmark.md (about 60 lines): what it measures, how to run it, how long a run takes, and results with the date, metab version, provider, and machine. The only home of benchmark figures; README and architecture documents link it.
- Link it from the README's Scale section.
- After the fdu provider registers (INVENTORY_PROVIDERS in bench_serving.py lists only python today), rerun with --provider fdu and add its results beside the Python baseline.
- Not a release gate; the performance loop stays the gate.
