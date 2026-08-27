---
title: v0.8.0 preserves release correctness and responsiveness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-019
  title: v0.8.0 preserves release correctness and responsiveness
  date: "2026-08-26"
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
    control: exact installed v0.7.1 with a measurement-only concurrency recorder adapter
    candidate: exact installed wheel from 5674cb6
    record: five backend pairs and three admissible browser profiles per installed build
  results:
    - metric: backend_first_row_s
      control_median: 0.573
      candidate_median: 0.552
      control_range: [0.561, 0.594]
      candidate_range: [0.543, 0.582]
      change_pct: -3.7
      overlapping: true
    - metric: backend_index_done_s
      control_median: 5.074
      candidate_median: 5.313
      control_range: [4.812, 6.178]
      candidate_range: [5.053, 5.667]
      change_pct: 4.7
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 132.2
      candidate_median: 132.5
      control_range: [131.4, 141.5]
      candidate_range: [131.2, 140.8]
      change_pct: 0.2
      overlapping: true
    - metric: browser_first_row_ms
      control_median: 179
      candidate_median: 224
      control_range: [127, 225]
      candidate_range: [177, 263]
      change_pct: 25.1
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 140
      candidate_median: 140
      control_range: [120, 192]
      candidate_range: [124, 156]
      change_pct: 0.0
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
      - retained file or Git navigation can converge on stale content after rapid replacement
      - deferred diff hydration can exceed its request bound or survive a replacement
      - collapsed diff rows can remain mounted while hidden
    notes: >-
      The candidate adds 4 KB of startup JavaScript at the comparison's reporting
      precision while keeping the startup script count at 22. One candidate run reaches
      384 ms for LCP and records 0.0047 CLS; its first row is 263 ms, its FCP is 140 ms,
      and it records no Long Task or blocking time. Every timing range overlaps and all
      candidate profiles pass the hard gate.
  verdict:
    decision: accepted
    primary_metric: every candidate backend and browser run passes correctness and hard responsiveness gates
    reason: >-
      The candidate returns identical ordered rows and tallies on an unchanged corpus,
      preserves backend timing and memory within overlapping ranges, records no Long
      Task, blocking time, failed fetch, rendered error, page exception, or collapsed
      hidden row, and passes every hard browser budget. The 384 ms LCP tail does not
      separate the candidate interval from v0.7.1 or cross a hard release gate.
    commit: 5674cb6
---
# v0.8.0 preserves release correctness and responsiveness

## Question

Does the installed v0.8.0 minor-release candidate preserve v0.7.1’s answers and remain
within the release responsiveness gates?

Yes. Five backend pairs return identical ordered rows and tallies, and all six visible
browser profiles pass every hard correctness and responsiveness gate.
The candidate records no Long Task, blocking time, failed fetch, rendered error,
uncaught page exception, or collapsed diff row mounted beneath a closed fold.

One candidate browser run reaches 384 ms for LCP and records 0.0047 CLS, while its first
row is 263 ms and FCP is 140 ms.
The full candidate and release ranges overlap, so this sample does not establish a
repeatable regression or improvement.
The tail remains visible in the release record even though it passes the hard release
gate.

## Exact provenance and corpus

The control is an installed wheel from tag `v0.7.1`. The candidate is an installed wheel
built from commit `5674cb6`, before any measurement record changed the working tree, and
reports `metab 0.7.2.dev57+5674cb6`. Both isolated environments contain identical
dependency versions under the repository’s supply-chain cutoff; only Metabrowser
differs. The first-party Metabrowser release is exempt from that cutoff.

The v0.7.1 recorder predates the request-class concurrency provenance required by the
current evidence policy.
For its browser runs only, the isolated installed copy uses the current `perf.js`, whose
only delta from v0.7.1 is that bounded measurement instrumentation.
The release application and server remain exact.
This is a measurement adapter, not product compatibility code.

Both builds use one project-shaped corpus assembled from the repository’s locked
installs and source.
Its physical fingerprint stays fixed at 148,581 files, 18,721 directories, and newest
modification time `1787788885.36`. Ignore rules admit 67,290 files and 3,912 directories
to Metabrowser.

The backend comparator alternates builds and accepts timings only after checking the
corpus fingerprint, required response fields, ordered rows, and tallies.
The browser comparison uses fresh processes, origins, and visible 1600×900 Chrome
profiles, with controlled trusted input through client quiescence.
The condition order is release/candidate, candidate/release, release/candidate.

## Backend result

All five pairs are valid.
Every timing and memory range overlaps, so the comparison makes no backend performance
claim.

| measure | v0.7.1 median (range) | candidate median (range) | result |
| --- | ---: | ---: | --- |
| first navigation row | 0.573 s (0.561–0.594) | 0.552 s (0.543–0.582) | no detected difference |
| index complete | 5.074 s (4.812–6.178) | 5.313 s (5.053–5.667) | no detected difference |
| peak RSS | 132.2 MB (131.4–141.5) | 132.5 MB (131.2–140.8) | no detected difference |
| worst overlap progress | 121.8 ms (65.4–147.1) | 121.7 ms (81.9–124.6) | every run passes |

The corpus fingerprint is identical before and after the comparison.
Ordered rows and tallies have zero differences and no required field is missing.

## Browser result

All three candidate profiles pass the hard gate.
The first-row, paint, request, transfer, and retained-memory ranges overlap.
Both builds issue 22 startup script requests; candidate startup JavaScript is 159 KB
instead of 155 KB because the expanded recorder and shipped browser work are on the
eager path. Both builds render the tree region once and retain the same 23 px
reserved-region shift and 124 px shipped-frame gap, which remain roadmap targets rather
than release regressions.

| measure | v0.7.1 median (range) | candidate median (range) | result |
| --- | ---: | ---: | --- |
| hard-gate passes | 3 of 3 | 3 of 3 | every run passes |
| first row | 179 ms (127–225) | 224 ms (177–263) | no detected difference |
| FCP | 140 ms (120–192) | 140 ms (124–156) | no detected difference |
| LCP | 140 ms (120–192) | 156 ms (124–384) | no detected difference; one candidate tail |
| longest Long Task | 0 ms | 0 ms | unchanged |
| blocking time | 0 ms | 0 ms | unchanged |
| startup scripts | 22 | 22 | unchanged |
| startup JavaScript | 155 KB | 159 KB | 4 KB larger |
| all requests | 81 (67–84) | 83 (75–83) | ranges overlap |
| all transfer | 488 KB (473–495) | 484 KB (451–500) | ranges overlap |
| retained heap after GC | 4.9 MB (4.0–4.9) | 4.6 MB (4.2–4.9) | ranges overlap |

## Decision

Accept the candidate.
The minor release adds the retained-navigation, diff-rendering, Git-summary, Source, and
performance-gate work while preserving semantic responses, backend behavior, retained
memory, rendering count, and every hard browser budget.

The one candidate LCP tail remains part of the release record.
It does not separate the candidate interval from the release, create a Long Task or
blocking time, fail a fetch, render an error, throw an exception, or cross a hard
release budget.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
