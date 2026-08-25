---
title: Release stabilization bounds tally work without losing the performance win
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-016
  title: Release stabilization bounds tally work without losing the performance win
  date: "2026-08-24"
  hypotheses:
    - H58
    - H59
    - H61
    - H62
    - H63
  subject:
    corpus: fingerprinted project-shaped tree tree-48d6a4c7-mtime-0820
    corpus_files: 123658
    corpus_dirs: 15601
    host_system: Darwin 25.5.0
    browser: headed Chrome driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 4
    interleaved: true
    control: exact installed v0.6.0 and pre-stabilization main c123ae6
    candidate: exact installed wheel from 9edff6b
    record: five backend pairs per release control, ten c123ae6 overlap pairs, and four admissible browser profiles per installed build
  results:
    - metric: backend_v060_first_row_s
      control_median: 1.075
      candidate_median: 0.571
      control_range: [0.792, 1.600]
      candidate_range: [0.541, 0.579]
      change_pct: -46.9
      overlapping: false
    - metric: backend_v060_index_done_s
      control_median: 7.859
      candidate_median: 3.998
      control_range: [6.963, 9.947]
      candidate_range: [3.977, 4.569]
      change_pct: -49.1
      overlapping: false
    - metric: backend_v060_peak_rss_mb
      control_median: 126.3
      candidate_median: 123.5
      control_range: [124.5, 126.5]
      candidate_range: [122.4, 123.9]
      change_pct: -2.2
      overlapping: false
    - metric: backend_c123_tally_overlap_progress_max_ms
      control_median: 430.5
      candidate_median: 96.7
      control_range: [363.8, 547.3]
      candidate_range: [52.4, 156.0]
      change_pct: -77.5
      overlapping: false
    - metric: browser_hard_gate_pass_rate_pct
      control_median: 0
      candidate_median: 100
      control_range: [0, 0]
      candidate_range: [100, 100]
      overlapping: false
    - metric: browser_first_row_ms
      control_median: 962
      candidate_median: 239
      control_range: [359, 1863]
      candidate_range: [211, 503]
      change_pct: -75.2
      overlapping: true
    - metric: browser_fcp_ms
      control_median: 308
      candidate_median: 166
      control_range: [168, 592]
      candidate_range: [152, 268]
      change_pct: -46.1
      overlapping: true
    - metric: browser_lcp_ms
      control_median: 862
      candidate_median: 166
      control_range: [396, 1900]
      candidate_range: [152, 268]
      change_pct: -80.7
      overlapping: false
    - metric: browser_rendered_preview_errors
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
    - metric: browser_page_exceptions
      control_median: 0
      candidate_median: 0
      control_range: [0, 0]
      candidate_range: [0, 0]
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes:
      - a nonblocking cache miss still needs cooperative yielding in its CPU worker
      - a measurement adapter can alter the release contract it is supposed to observe
      - a broad process-name cleanup can terminate a server outside the harness
    notes: >-
      The first exact candidate failed one of five release backend pairs, which triggered
      H61 rather than a wider budget. Later review invalidated the original v0.6.0 browser
      profiles because their measurement adapter initialized the SDK namespace early.
      Harness 15 makes rendered errors and uncaught exceptions hard failures, preserves
      the release namespace handoff, and isolates each external server process.
  verdict:
    decision: accepted
    primary_metric: every exact candidate backend and browser run passes its responsiveness and correctness gates
    reason: >-
      The final installed candidate returns identical rows and tallies, keeps overlap
      progress below 200 ms in every backend run, records no Long Task, rendered error,
      or page exception in four visible browser runs, and improves release-level loading,
      indexing, startup assets, and retained memory without weakening a gate.
    commit: 9edff6b
---
# Release stabilization bounds tally work without losing the performance win

## Question

Does the exact release candidate preserve the performance work on `main`, remain
responsive when tally requests overlap, and render without hidden browser failures?

Yes. The exact installed candidate returns the same ordered rows and tallies as both
controls, keeps every overlap progress probe below 200 ms, and passes every hard browser
gate in four visible runs.
It records no Long Task, rendered preview error, uncaught page exception, failed fetch,
readiness gap, or incomplete catalog.

Two rejected results are part of that answer.
An intermediate candidate crossed the backend responsiveness gate once, which led to
bounded cooperative yielding.
The first v0.6.0 browser adapter produced plausible timing JSON while rendering an error
panel; the corrected harness now rejects that state directly.

## Exact provenance and corpus

The release control is an installed wheel built from tag `v0.6.0`. The pre-stabilization
control is an installed wheel built from merged-main commit `c123ae6`. The candidate is
an installed wheel built from commit `9edff6b` and reports `metab 0.6.1.dev74+9edff6b`.

All backend and browser runs use the same fingerprinted project-shaped corpus.
Its physical fingerprint is unchanged at 123,658 files, 15,601 directories, and newest
modification time `1787252400.0`. The modification times are deliberately fixed inside
the seven-day recency window and outside the one-day boundary, so a clock crossing
cannot change tally semantics between builds.
Ordinary ignore rules admit 55,835 files and 3,260 directories to the application
inventory.

The backend comparator alternates builds and admits timings only after verifying the
corpus fingerprint, ordered rows, and tallies.
The browser comparison uses fresh ports, fresh Chrome profiles, a visible 1600×900
viewport, and trusted input from first usable state through client quiescence.

## Correcting the release measurement adapter

The first v0.6.0 adapter copied the current recorder over the release’s `perf.js`. That
changed an internal ordering contract: v0.6.0 loads its recorder before the plugin SDK
and hands it through `window.metabrowserPerf`, while the current recorder expects the
SDK namespace to exist.
The copied recorder created `window.metabrowser` early, so the release SDK’s double-load
guard returned without registering its API.

The page then rendered `getRegisteredView is not a function`; eight built-in plugin
modules also threw because `registerView` was absent.
The old harness recorded the error detail as the LCP element and still marked the
profile valid because it gated network, readiness, and responsiveness, not rendered
error states.

Harness 15 closes both holes:

- `rendered_preview_errors` counts error states in the main preview panel and is
  required to be zero;
- `page_exceptions` counts Chrome `Runtime.exceptionThrown` events from navigation
  through profile export and is required to be zero;
- external builds run from the served root, not the candidate checkout; and
- server cleanup verifies the recorded PID, executable, root, and port rather than
  killing every matching process name.

The corrected v0.6.0 adapter is rebuilt from the exact tag.
Its measurement-only recorder preserves `window.metabrowserPerf` until the release SDK
initializes, then exposes the current snapshot to the probe.
The broken adapter now fails with one rendered error and eight page exceptions.
All eight admissible control and candidate profiles record zero for both metrics.
This is test instrumentation, not a production compatibility layer, as required by the
[Web Performance Framework](../../../docs/web-performance-framework.md).

## Backend result

Five interleaved release pairs produce identical ordered rows and tallies.
The candidate returns the first navigation row 47% sooner, completes indexing 49%
sooner, and retains 2% less peak memory.
Process-start ranges overlap, so the data make no process-start claim.

| measure | v0.6.0 median (range) | candidate median (range) | result |
| --- | ---: | ---: | --- |
| process to serving | 0.403 s (0.347–0.834) | 0.428 s (0.345–0.713) | no detected difference |
| first navigation row | 1.075 s (0.792–1.600) | **0.571 s (0.541–0.579)** | 47% sooner |
| index complete | 7.859 s (6.963–9.947) | **3.998 s (3.977–4.569)** | 49% sooner |
| peak RSS | 126.3 MB (124.5–126.5) | **123.5 MB (122.4–123.9)** | 2% lower |
| overlap progress | release did not expose the probe | **88.0 ms (63.9–115.7)** | every candidate run passes |

Across two five-pair comparisons with `c123ae6`, the control’s worst progress probe per
run is 363.8–547.3 ms and the candidate’s is 52.4–156.0 ms.
The candidate’s median is 96.7 ms against 430.5 ms.
One candidate index-completion sample reaches 11.192 s, but its overlap progress stays
at 114.8 ms; the next ten candidate overlap probes remain below 156.0 ms.
The tail is retained without turning it into a reproducible regression.

## Browser result

The candidate passes every hard gate in all four admissible profiles.
The old release fails modern asset and tool-readiness gates in every run and reproduces
a 1,553 ms Long Task in one run.
The comparison makes no claim that a release lacking those modern surfaces should
satisfy them; it shows that the candidate both supplies the surfaces and remains
responsive.

| measure | v0.6.0 median (range) | candidate median (range) | result |
| --- | ---: | ---: | --- |
| hard-gate passes | 0 of 4 | **4 of 4** | candidate passes every run |
| first row | 962 ms (359–1,863) | **239 ms (211–503)** | lower median; ranges overlap |
| FCP | 308 ms (168–592) | **166 ms (152–268)** | lower median; ranges overlap |
| LCP | 862 ms (396–1,900) | **166 ms (152–268)** | ranges do not overlap |
| longest Long Task | 40 ms (0–1,553) | **0 ms (0–0)** | no candidate Long Task |
| worst interaction | 36 ms (0–120) | **8 ms (0–24)** | every candidate run passes |
| blocked main-thread share | 0.1% (0–32.4) | **0% (0–0)** | no candidate blocking |
| rendered preview errors | 0 | 0 | clean control and candidate |
| uncaught page exceptions | 0 | 0 | clean control and candidate |
| startup scripts | 74 | **22** | 70% fewer |
| startup JavaScript | 332 KB | **154 KB** | 54% less |
| all requests | 138 (114–154) | **81 (75–125)** | 41% lower median |
| all transfer | 519 KB (504–668) | **473 KB (440–509)** | 9% lower median |

One candidate first-row sample is 503 ms, three milliseconds above the 500 ms roadmap
target. That target is not a hard release budget; FCP is 268 ms in the same run, no task
or interaction crosses 200 ms, and the full candidate range remains below the release
median. The tail stays visible in the record.

## Initial-load highlighting and changelog policy

The final candidate also treats the first inventory as a navigation baseline.
Snapshot rows and walker upserts remain neutral until the first terminal inventory
signal; the first later live insert receives the yellow change flash.
Browser behavior tests cover both completion paths, and all four exact candidate
profiles continue to pass the hard performance and correctness gates.

The changelog records the aggregate v0.6.0-to-v0.7.0 performance and observable API
changes. It does not list the intermediate lock regression, the invalid measurement
adapter, or the initial-load flash correction as separate shipped features: each was an
issue introduced and corrected inside this unreleased performance/refactor cycle.

## Verdict

**Accepted.** Commit `9edff6b` preserves the release-level performance improvement,
bounds unrelated request latency, restores neutral initial-load highlighting, and passes
the corrected browser gate without a rendered error or uncaught exception.
The rejected intermediate and invalid adapter records remain useful because they prove
the gates catch the failures they were added to prevent.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
