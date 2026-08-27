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
    candidate: exact installed wheel from ec2ede9
    record: five backend pairs and three admissible browser profiles per installed build
  results:
    - metric: backend_first_row_s
      control_median: 0.556
      candidate_median: 0.560
      control_range: [0.544, 1.027]
      candidate_range: [0.542, 0.582]
      change_pct: 0.7
      overlapping: true
    - metric: backend_index_done_s
      control_median: 6.129
      candidate_median: 5.903
      control_range: [5.579, 7.089]
      candidate_range: [5.808, 6.441]
      change_pct: -3.7
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 132.7
      candidate_median: 132.1
      control_range: [132.0, 138.3]
      candidate_range: [132.0, 133.0]
      change_pct: -0.5
      overlapping: true
    - metric: browser_first_row_ms
      control_median: 313
      candidate_median: 276
      control_range: [223, 389]
      candidate_range: [223, 930]
      change_pct: -11.8
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 228
      candidate_median: 184
      control_range: [152, 240]
      candidate_range: [184, 392]
      change_pct: -19.3
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
      precision while keeping the startup script count at 22. One cold candidate run
      reaches 930 ms for first row, 392 ms for FCP, and a 223 ms animation frame; the
      other two match the release floor, the intervals overlap, and no candidate run
      records a Long Task or blocking time. The outlier is retained as a release caveat
      rather than averaged away or promoted to a repeatable regression.
  verdict:
    decision: accepted
    primary_metric: every candidate backend and browser run passes correctness and hard responsiveness gates
    reason: >-
      The candidate returns identical ordered rows and tallies on an unchanged corpus,
      preserves backend timing and memory within overlapping ranges, records no Long
      Task, blocking time, failed fetch, rendered error, page exception, or collapsed
      hidden row, and passes every hard browser budget. The one cold-start tail is not
      repeatable and crosses roadmap targets rather than release gates.
    commit: ec2ede9
---
# v0.8.0 preserves release correctness and responsiveness

## Question

Does the installed v0.8.0 minor-release candidate preserve v0.7.1’s answers and remain
within the release responsiveness gates?

Yes. Five backend pairs return identical ordered rows and tallies, and all six visible
browser profiles pass every hard correctness and responsiveness gate.
The candidate records no Long Task, blocking time, failed fetch, rendered error,
uncaught page exception, or collapsed diff row mounted beneath a closed fold.

One candidate browser run is a cold-start tail: first row reaches 930 ms, FCP reaches
392 ms, and the longest animation frame reaches 223 ms.
The other two candidate runs reach first row in 223–276 ms and FCP in 184 ms.
The full candidate and release ranges overlap, so this sample does not establish a
repeatable regression or improvement.
The outlier remains visible as a release caveat because it misses roadmap targets even
though it passes the hard release gate.

## Exact provenance and corpus

The control is an installed wheel from tag `v0.7.1`. The candidate is an installed wheel
built from commit `ec2ede9`, before any measurement record changed the working tree, and
reports `metab 0.7.2.dev55+ec2ede9`. Both isolated environments contain identical
dependency versions; only Metabrowser differs.

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
| first navigation row | 0.556 s (0.544–1.027) | 0.560 s (0.542–0.582) | no detected difference |
| index complete | 6.129 s (5.579–7.089) | 5.903 s (5.808–6.441) | no detected difference |
| peak RSS | 132.7 MB (132.0–138.3) | 132.1 MB (132.0–133.0) | no detected difference |
| worst overlap progress | 69.4 ms (65.8–154.8) | 108.9 ms (55.4–162.1) | every run passes |

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
| first row | 313 ms (223–389) | 276 ms (223–930) | no detected difference; one candidate tail |
| FCP | 228 ms (152–240) | 184 ms (184–392) | no detected difference; one candidate tail |
| LCP | 228 ms (152–240) | 184 ms (184–392) | no detected difference; one candidate tail |
| longest Long Task | 0 ms | 0 ms | unchanged |
| blocking time | 0 ms | 0 ms | unchanged |
| startup scripts | 22 | 22 | unchanged |
| startup JavaScript | 155 KB | 159 KB | 4 KB larger |
| all requests | 85 | 85 (85–102) | ranges overlap |
| all transfer | 493 KB (485–499) | 507 KB (498–515) | ranges overlap |
| retained heap after GC | 4.9 MB (4.8–4.9) | 4.9 MB (4.8–4.9) | unchanged |

## Decision

Accept the candidate.
The minor release adds the retained-navigation, diff-rendering, Git-summary, Source, and
performance-gate work while preserving semantic responses, backend behavior, retained
memory, rendering count, and every hard browser budget.

The one candidate cold-start tail remains part of the release record.
It does not repeat, separate the candidate interval from the release, create a Long Task
or blocking time, fail a fetch, render an error, throw an exception, or cross a hard
release budget.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
