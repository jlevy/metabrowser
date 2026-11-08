---
title: Measure Provider Cost for a Visible PR Core Batch
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-048
  title: Measure Provider Cost for a Visible PR Core Batch
  date: '2026-11-04'
  hypotheses:
  - H77
  subject:
    corpus: Public jlevy/metabrowser, fixed eight-PR cohort.
    corpus_files: 1245
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0, CPython 3.14.7, Git 2.50.1, Node 24.19.0
    browser: No browser. Live gh API commands.
  method:
    runs_per_condition: 3
    interleaved: true
    control: Unchanged catalog query and one REST PR core request.
    candidate: Diagnostic GraphQL requests for one core, eight cores or the catalog plus the same eight
      cores.
    record: exp-045-049-focused-samples.jsonl
  results:
  - metric: catalog_response_decoded_bytes
    control_median: 60680
    candidate_median: 97423
    control_range:
    - 60680
    - 60680
    candidate_range:
    - 97422
    - 97423
    overlapping: false
  - metric: catalog_provider_ms
    control_median: 968.42
    candidate_median: 1193.71
    control_range:
    - 957.93
    - 1050.03
    candidate_range:
    - 1050.65
    - 1268.99
    overlapping: false
  - metric: selected_core_decoded_bytes
    control_median: 19764
    candidate_median: 4660
    control_range:
    - 19764
    - 19764
    candidate_range:
    - 4660
    - 4660
    overlapping: false
  - metric: selected_core_provider_ms
    control_median: 565.26
    candidate_median: 631.1
    control_range:
    - 464.57
    - 663.4
    candidate_range:
    - 577.84
    - 682.8
    overlapping: true
  verdict:
    decision: baseline
    primary_metric: catalog_response_decoded_bytes
    reason: The live provider diagnostic establishes a bounded batch cost. It leaves product prefetch
      and click outcomes open.
---
`mb-oywk` extends H77 with a provider-only diagnosis.
The fixed public cohort was #298, #297, #295, #294, #293, #292, #291 and #290. Six cases
ran three times each, with 18 API requests, 36 diagnostic account checks and no retries.
The selected #294 core validated identically in all 12 observations that returned it.
The other seven were compared across GraphQL variants and repeats.
[Public repository PRs](https://github.com/jlevy/metabrowser/pulls?q=is%3Apr)

| Provider case | Duration range (ms) | Decoded body bytes |
| --- | ---: | ---: |
| REST one core | 465–663 | 19,764 |
| GraphQL one core | 578–683 | 4,660 |
| GraphQL eight cores | 894–1,068 | 36,865–36,866 |
| Stock catalog | 958–1,050 | 60,680 |
| Catalog with cost field | 865–1,145 | 60,795 |
| Catalog plus eight cores | 1,051–1,269 | 97,422–97,423 |

GraphQL cases with the cost field each reported one point.
These are decoded responses and provider elapsed times.
REST quota, compressed wire bytes, browser rendering and click latency were outside the
measurement.

The separate batch keeps the stock catalog response size and provides a candidate for
testing background preparation after summaries arrive.
Eight was the fixed diagnostic cohort.
A product batch size, cache lifetime and actual click benefit remain open.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
