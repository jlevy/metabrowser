---
title: v0.7.1 preserves release correctness and responsiveness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-017
  title: v0.7.1 preserves release correctness and responsiveness
  date: "2026-08-24"
  hypotheses: []
  subject:
    corpus: fingerprinted project-shaped tree tree-f1184cd1
    corpus_files: 123573
    corpus_dirs: 15601
    host_system: Darwin 25.5.0
    browser: headed Chrome driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: true
    control: exact installed v0.7.0
    candidate: exact installed wheel from 7eb4157
    record: five backend pairs and three admissible browser profiles per installed build
  results:
    - metric: backend_first_row_s
      control_median: 0.571
      candidate_median: 0.545
      control_range: [0.295, 0.586]
      candidate_range: [0.279, 0.567]
      change_pct: -4.6
      overlapping: true
    - metric: backend_index_done_s
      control_median: 4.277
      candidate_median: 4.248
      control_range: [4.257, 4.860]
      candidate_range: [3.935, 4.501]
      change_pct: -0.7
      overlapping: true
    - metric: backend_peak_rss_mb
      control_median: 123.0
      candidate_median: 122.9
      control_range: [122.6, 130.9]
      candidate_range: [122.4, 130.0]
      change_pct: -0.1
      overlapping: true
    - metric: browser_first_row_ms
      control_median: 162
      candidate_median: 213
      control_range: [152, 175]
      candidate_range: [187, 230]
      change_pct: 31.5
      overlapping: false
    - metric: browser_fcp_ms
      control_median: 136
      candidate_median: 152
      control_range: [128, 140]
      candidate_range: [128, 180]
      change_pct: 11.8
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
      - a Git commit view can request its on-demand diff renderer after a newer selection replaces it
    notes: >-
      The patch adds two hidden menu nodes and no startup request. The browser sample
      detects a 51 ms first-row delay, while FCP and LCP ranges overlap, transfer and
      startup script counts remain unchanged, and every candidate run remains below the
      hard responsiveness budgets. The on-demand Git fix does not join the startup asset
      path.
  verdict:
    decision: accepted
    primary_metric: every candidate backend and browser run passes correctness and hard responsiveness gates
    reason: >-
      The candidate returns identical ordered rows and tallies, preserves memory and
      backend timing within overlapping ranges, records no Long Task, failed fetch,
      rendered error, or page exception, and keeps first row below 230 ms in every run.
      The detected 51 ms browser-startup movement is retained as a release caveat rather
      than hidden by medians; it does not cross a hard budget or accompany a request,
      transfer, memory, paint, or blocking regression.
    commit: 7eb4157
---
# v0.7.1 preserves release correctness and responsiveness

## Question

Does the installed v0.7.1 patch candidate preserve v0.7.0’s answers and remain within
the release responsiveness gates?

Yes. Five backend pairs return identical ordered rows and tallies, and all six visible
browser profiles pass every hard correctness and responsiveness gate.
The candidate records no Long Task, failed fetch, rendered error, or uncaught page
exception.

The browser sample also detects a 51 ms first-row delay.
That result is retained rather than averaged away: the release median is 162 ms and the
candidate median is 213 ms, with non-overlapping ranges.
FCP and LCP ranges overlap, and the candidate adds no startup request or transferred
byte at the comparison’s reporting precision.

## Exact provenance and corpus

The control is an installed wheel from tag `v0.7.0`. The candidate is an installed wheel
built from commit `7eb4157` and reports `metab 0.7.1.dev3+7eb4157` before the checkout
annotation added by the local comparison directory.

Both builds use one fingerprinted project-shaped corpus.
Its physical fingerprint stays fixed at 123,573 files, 15,601 directories, and newest
modification time `1787639598.93`. Ignore rules admit 55,835 files and 3,260 directories
to Metabrowser.

The backend comparator alternates builds and accepts timing only after checking the
corpus fingerprint, response fields, ordered rows, and tallies.
The browser comparison uses fresh processes, origins, visible 1600×900 Chrome profiles,
and controlled trusted input through client quiescence.

## Backend result

All five pairs are valid.
Every timing and memory range overlaps, so the comparison makes no backend performance
claim.

| measure | v0.7.0 median (range) | candidate median (range) | result |
| --- | ---: | ---: | --- |
| first navigation row | 0.571 s (0.295–0.586) | 0.545 s (0.279–0.567) | no detected difference |
| index complete | 4.277 s (4.257–4.860) | 4.248 s (3.935–4.501) | no detected difference |
| peak RSS | 123.0 MB (122.6–130.9) | 122.9 MB (122.4–130.0) | no detected difference |
| worst overlap progress | 75.4 ms (53.1–141.5) | 87.3 ms (71.6–131.6) | every run passes |

The corpus fingerprint is identical before and after the comparison.
Ordered rows and tallies have zero differences and no required field is missing.

## Browser result

All three candidate profiles pass the hard gate.
The candidate first-row interval is 51 ms later at the median, while the FCP and LCP
intervals overlap. Both builds issue 22 startup script requests transferring 154 KB,
render the tree region once, and retain the same 23 px reserved-region shift and 100 px
shipped-frame gap. Those last two are known roadmap targets, not release regressions.

| measure | v0.7.0 median (range) | candidate median (range) | result |
| --- | ---: | ---: | --- |
| hard-gate passes | 3 of 3 | 3 of 3 | every run passes |
| first row | 162 ms (152–175) | 213 ms (187–230) | 51 ms later |
| FCP | 136 ms (128–140) | 152 ms (128–180) | no detected difference |
| LCP | 136 ms (128–140) | 152 ms (128–180) | no detected difference |
| longest Long Task | 0 ms | 0 ms | unchanged |
| startup scripts | 22 | 22 | unchanged |
| startup JavaScript | 154 KB | 154 KB | unchanged |
| all requests | 79 (72–82) | 80 (75–80) | ranges overlap |
| all transfer | 483 KB (481–507) | 482 KB (443–483) | ranges overlap |
| retained heap after GC | 4.5 MB (4.4–4.6) | 4.6 MB (3.9–4.6) | ranges overlap |

## Decision

Accept the candidate.
The patch restores a broken commit-diff path, removes a duplicate tooltip, and adds a
build identity in an already-hidden menu.
It preserves semantic responses, startup assets, memory, rendering count, and all hard
browser budgets.

The observed first-row movement is real for this sample and belongs in the record.
It does not cross a hard budget, appear in FCP or LCP as a separated interval, or
accompany a network, transfer, retained-memory, rendering, or blocking change.
The candidate’s worst first row is 230 ms against the 500 ms roadmap target.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
