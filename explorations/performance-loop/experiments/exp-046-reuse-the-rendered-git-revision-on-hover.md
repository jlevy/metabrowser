---
title: Reuse the Rendered Git Revision on Hover
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-046
  title: Reuse the Rendered Git Revision on Hover
  date: '2026-11-04'
  hypotheses:
  - H78
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
    control: Installed clean main wheel at db52ec09. Wheel and source hashes in the sample record.
    candidate: Installed candidate03 wheel based on db52ec09. Wheel and source hashes in the sample record.
    record: exp-045-049-focused-samples.jsonl
  results:
  - metric: reentry_comparisons
    control_median: 1
    candidate_median: 0
    control_range:
    - 1
    - 1
    candidate_range:
    - 0
    - 0
    overlapping: false
  verdict:
    decision: accepted
    primary_metric: reentry_comparisons
    reason: All five final candidate reentries reused the rendered comparison. Each paired main run fetched
      one extra comparison.
---
H78 was registered as `mb-wpyg` before implementation.
Three unchanged-build controls moved the trusted pointer away from the selected row and
back after the exact revision had rendered.
Each started a second matching comparison after handoff.
Clearing the completed preparation slot had left hover free to prepare the revision
again.

Hover still prepares tooltip metadata and other rows.
A row already rendered under the current Git preview claim reuses its comparison.
On transfer to a different preview owner, pending comparison and deferred hydration work
cancel while the visible Git content remains available for handoff.
Returning to Git can prepare the same revision under the new claim.

Across five final pairs the stable post-handoff reentry issued one extra matching
comparison on main and zero on candidate.
Main transferred 281,434 decoded comparison bytes per duplicate.
The expected main error is retained in the samples.
The final candidate also contains the connected staging change in exp-047. The exact
request count establishes reuse independently of the combined paint result.

Three Git correctness captures passed the cold and pointer-prepared navigation, deferred
cancellation and Git/Files round trip checks.
A 250 ms latency fixture applied only to the deferred correctness phase and was reset
after each stress. Those captures carry no timing claim.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
