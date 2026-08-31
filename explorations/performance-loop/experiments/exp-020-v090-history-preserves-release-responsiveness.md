---
title: v0.9 Git history preserves release correctness and responsiveness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-020
  title: v0.9 Git history preserves release correctness and responsiveness
  date: "2026-08-27"
  hypotheses: []
  subject:
    corpus: fingerprinted project-shaped tree tree-114a927f
    corpus_files: 148581
    corpus_dirs: 18721
    host_system: Darwin 25.5.0
    browser: headed Chrome 151.0.7922.109 driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: true
    control: exact installed v0.8.0
    candidate: exact installed wheel from 1c7bdf8
    record: five backend pairs and three admissible browser profiles per installed build
  results:
    - metric: backend_first_row_s
      control_median: 0.577
      candidate_median: 0.551
      control_range: [0.539, 0.823]
      candidate_range: [0.535, 0.568]
      change_pct: -4.5
      overlapping: true
    - metric: backend_index_done_s
      control_median: 5.122
      candidate_median: 5.086
      control_range: [4.767, 6.986]
      candidate_range: [4.785, 5.341]
      change_pct: -0.7
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 132.3
      candidate_median: 133.6
      control_range: [131.9, 141.4]
      candidate_range: [132.2, 141.1]
      change_pct: 1.0
      overlapping: true
    - metric: browser_first_row_ms
      control_median: 209
      candidate_median: 206
      control_range: [134, 297]
      candidate_range: [204, 263]
      change_pct: -1.4
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 132
      candidate_median: 164
      control_range: [128, 152]
      candidate_range: [152, 172]
      change_pct: 24.2
      overlapping: true
    - metric: browser_hard_gate_pass_rate_pct
      control_median: 100
      candidate_median: 100
      control_range: [100, 100]
      candidate_range: [100, 100]
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes:
      - an idle or resource-evicted server history session requires explicit recovery
      - an evicted browser page must replay from its graph-boundary checkpoint
      - a deep logical history requires physical scroll-segment rebasing
    notes: >-
      Startup remains 22 scripts and 159 KB. The candidate transfers 8 KB more
      JavaScript after on-demand work, keeps the same single tree-region paint, and
      retains the same 23 px reserved-region shift and 124 px shipped-frame gap. Those
      two layout values remain roadmap targets on both builds. Every timing range
      overlaps and all candidate profiles pass the hard gate.
  verdict:
    decision: accepted
    primary_metric: every candidate backend and browser run passes correctness and hard responsiveness gates
    reason: >-
      The candidate returns identical ordered rows and tallies on an unchanged corpus,
      preserves backend timing and memory within overlapping ranges, records no Long
      Task, blocking time, failed fetch, rendered error, page exception, or collapsed
      hidden row, and passes every hard browser budget.
    commit: 1c7bdf8
---
# v0.9 Git history preserves release correctness and responsiveness

## Question

Does the installed v0.9 Git-history candidate preserve v0.8.0’s answers and remain
within the release responsiveness gates?

Yes. Five backend pairs return identical ordered rows and tallies, and all six visible
browser profiles pass every hard correctness and responsiveness gate.
The candidate records no Long Task, blocking time, failed fetch, rendered error,
uncaught page exception, or collapsed diff row mounted beneath a closed fold.

## Exact provenance and corpus

The control is the first-party `metabrowser==0.8.0` wheel.
The candidate is the wheel built from exact commit `1c7bdf8`, before the measurement
ledger changed the working tree, and has package version `0.8.1.dev5+1c7bdf8`. Each
wheel is installed into a fresh isolated environment with the same dependency
resolution. The first-party Metabrowser release is exempt from the dependency cool-off
period.

Both builds use the unchanged project-shaped corpus retained from the v0.8.0 release
comparison. Its physical fingerprint remains 148,581 files, 18,721 directories, and
newest modification time `1787788885.36`. Ignore rules admit 67,290 files and 3,912
directories to Metabrowser.

The backend comparator alternates builds and accepts timings only after checking the
corpus fingerprint, required response fields, ordered rows, and tallies.
The browser comparison uses fresh processes, origins, and visible 1600 × 900 Chrome
profiles with controlled trusted input through client quiescence.
The condition order is release/candidate, candidate/release, release/candidate.

## Backend result

All five pairs are valid.
Every timing and memory range overlaps, so the comparison makes no backend performance
claim.

| measure | v0.8.0 median (range) | candidate median (range) | result |
| --- | ---: | ---: | --- |
| first navigation row | 0.577 s (0.539–0.823) | 0.551 s (0.535–0.568) | no detected difference |
| index complete | 5.122 s (4.767–6.986) | 5.086 s (4.785–5.341) | no detected difference |
| peak RSS | 132.3 MB (131.9–141.4) | 133.6 MB (132.2–141.1) | no detected difference |
| worst overlap progress | 60.9 ms (52.0–104.0) | 102.8 ms (80.6–130.2) | every run passes |

The corpus fingerprint is identical before and after the comparison.
Ordered rows and tallies have zero differences, and no required field is missing.

## Browser result

All three candidate profiles pass the hard gate.
First-row, paint, request, transfer, and retained-memory ranges overlap.
Both builds issue 22 startup script requests and transfer 159 KB of startup JavaScript.
The candidate transfers 324 KB of JavaScript in total instead of 316 KB after on-demand
activity. Both builds render the tree region once and retain the same 23 px
reserved-region shift and 124 px shipped-frame gap, which remain roadmap targets rather
than release regressions.

| measure | v0.8.0 median (range) | candidate median (range) | result |
| --- | ---: | ---: | --- |
| hard-gate passes | 3 of 3 | 3 of 3 | every run passes |
| first row | 209 ms (134–297) | 206 ms (204–263) | no detected difference |
| FCP | 132 ms (128–152) | 164 ms (152–172) | no separated interval |
| LCP | 132 ms (128–152) | 164 ms (152–172) | no separated interval |
| longest Long Task | 0 ms | 0 ms | unchanged |
| blocking time | 0 ms | 0 ms | unchanged |
| startup scripts | 22 | 22 | unchanged |
| startup JavaScript | 159 KB | 159 KB | unchanged |
| all requests | 85 (77–86) | 86 (86–86) | ranges meet |
| all transfer | 492 KB (475–539) | 490 KB (490–508) | ranges overlap |
| retained heap after GC | 4.7 MB (4.6–4.9) | 4.6 MB (4.6–4.9) | ranges overlap |

## Decision

Accept the candidate.
The minor release can expose complete Git history while keeping semantic responses,
startup work, backend behavior, retained memory, rendering count, and every hard browser
budget within the release contract.

The comparison makes no timing improvement claim.
FCP and LCP ranges meet at 152 ms, and the candidate stays far inside the hard paint
budget without a Long Task or blocking time.
The unchanged 23 px reserved-region shift and 124 px shipped-frame gap remain explicit
roadmap work.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
