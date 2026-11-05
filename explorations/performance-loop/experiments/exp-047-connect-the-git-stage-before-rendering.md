---
title: Connect the Git Stage Before Rendering the First Screen
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-047
  title: Connect the Git Stage Before Rendering the First Screen
  date: '2026-11-04'
  hypotheses:
  - H79
  subject:
    corpus: Frozen public jlevy/metabrowser corpus at db52ec09cf839269da3a56fd396e44f3092995a9 with identical
      held Git, file and catalog inputs for each condition.
    corpus_files: 1245
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0, CPython 3.14.7, Git 2.50.1, Node 24.19.0
    browser: Visible Google Chrome 152, CDP-driven with a fresh profile per run.
    viewport: 1600x900
    cold: true
  method:
    runs_per_condition: 5
    interleaved: true
    control: Installed clean main wheel at db52ec09. Wheel and source hashes in the sample record. An
      isolated same-payload diagnostic also rendered into a detached stage on main.
    candidate: Installed candidate03 wheel based on db52ec09. Wheel and source hashes in the sample record.
      The diagnostic connected a hidden stage using the same main artifact and payload.
    record: exp-045-049-focused-samples.jsonl
  results:
  - metric: trusted_git_click_to_paint_ms
    control_median: 365.7
    candidate_median: 238.2
    control_range:
    - 357.7
    - 387
    candidate_range:
    - 236.3
    - 246.6
    overlapping: false
  - metric: longest_task_ms
    control_median: 118
    candidate_median: 0
    control_range:
    - 117
    - 118
    candidate_range:
    - 0
    - 0
    overlapping: false
  - metric: isolated_exact_paint_ms
    control_median: 305.2
    candidate_median: 73.9
    control_range:
    - 178.9
    - 324.4
    candidate_range:
    - 71.5
    - 75.6
    overlapping: false
  - metric: isolated_initial_models
    control_median: 50
    candidate_median: 4
    control_range:
    - 50
    - 50
    candidate_range:
    - 4
    - 4
    overlapping: false
  - metric: isolated_initial_projections
    control_median: 88
    candidate_median: 7
    control_range:
    - 88
    - 88
    candidate_range:
    - 7
    - 7
    overlapping: false
  verdict:
    decision: accepted
    primary_metric: trusted_git_click_to_paint_ms
    reason: Same-payload controls isolate first-screen work. Five final Git pairs painted sooner with
      no observed Long Task.
---
H79 was registered as `mb-envd` before implementation.
In three unchanged-build selections the recorder observed 229–240 ms Long Tasks.
A detached stage had no useful viewport geometry, so the first render constructed all
ready file models.

The separate diagnostic used the exact same held 281,434-byte comparison, with 55 files
and 50 initial patches, and the same renderer, assets and layout.
Three detached mounts painted the exact first text and filled viewport in 178.9–324.4
ms. Three connected hidden mounts took 71.5–75.6 ms.
The diagnostic cut initial models from 50 to 4 and projections from 88 to 7, with
107–240 ms Long Tasks in detached mounts and none in connected mounts.
Neither condition issued a new comparison.
The original Git content remained visible during the diagnostic.

The candidate connects the hidden comparison stage under the current preview claim
before mounting the diff.
It discards stale work and keeps the previous content visible until handoff.
In five final trusted navigation pairs, click to exact painted revision was 236.3–246.6
ms on candidate and 357.7–387.0 ms on main.
Candidate recorded zero Long Tasks.
Main recorded a longest task of 117–118 ms.
This whole-path result includes exp-046 and uses one selected revision.
[Public commit](https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9)

Three Git correctness captures used the scoped deferred stress fixture described in
exp-046. Three file-view correctness captures also passed cold source, structured and
Markdown views and cached source.
The generic performance gates run separately.

The separate initial-load comparator passed every hard gate across three interleaved
pairs on a generated repository-shaped corpus (shape 1, 24,396 files including ignored
installs).
Both wheels ran in one isolated interpreter with identical dependency records.
The folder startup tier remained 20 scripts and 175 KiB rounded in both conditions.
The focused Git profiles are still separate from those admissible initial-load records.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
