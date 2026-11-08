---
title: Publish the Selected PR Description Before the Full Conversation
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-045
  title: Publish the Selected PR Description Before the Full Conversation
  date: '2026-11-04'
  hypotheses:
  - H77
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
    runs_per_condition: 3
    interleaved: true
    control: Installed clean main wheel at db52ec09. Wheel and source hashes in the sample record.
    candidate: Installed candidate03 wheel based on db52ec09. Wheel and source hashes in the sample record.
    record: exp-045-049-focused-samples.jsonl
  results:
  - metric: selected_description_ms
    control_median: 4081.7
    candidate_median: 1324
    control_range:
    - 3063.8
    - 4089.3
    candidate_range:
    - 1265.5
    - 1557.6
    overlapping: false
  - metric: full_conversation_ms
    control_median: 4082
    candidate_median: 4065.8
    control_range:
    - 3064.1
    - 4089.6
    candidate_range:
    - 4065.7
    - 4065.9
    overlapping: true
  - metric: blank_frames_with_useful_prior_pr
    control_median: 364
    candidate_median: 0
    control_range:
    - 364
    - 365
    candidate_range:
    - 0
    - 0
    overlapping: false
  verdict:
    decision: accepted
    primary_metric: selected_description_ms
    reason: Early description and prior-content retention passed the paired tests. One full-Conversation
      outlier passed its single prescribed rerun. No full-completion speedup is claimed.
---
## Hypothesis and control

H77 was registered as `mb-tgn3` before implementation.
A ready Pulls catalog carries summaries.
In three unchanged-build comparisons for the same PR, a missing full record took
3,082–4,091 ms to paint the description, while a held full record took 42–53 ms.
This isolated the initial full-record miss on the tested path.
The selected refresh can publish validated core for the current source and account while
comments, reviews, and checks remain explicitly pending.
The durable full record still comes from the complete refresh.
[Public selected PR](https://github.com/jlevy/metabrowser/pull/294)

## Results

The three v7 pairs used a fresh server, origin and browser profile, natural asset
loading, and an absent selected record.
A trusted click starts both clocks.
The description requires the exact header and a literal body witness.
Full Conversation additionally requires its completion marker.
Fresh origins leave filesystem and Git caches outside the cold declaration.

| Pair | Description main / candidate (ms) | Full Conversation main / candidate (ms) |
| --- | ---: | ---: |
| 1 | 3063.8 / 1557.6 | 3064.1 / 4065.8 |
| 2 | 4089.3 / 1265.5 | 4089.6 / 4065.9 |
| 3 | 4081.7 / 1324.0 | 4082.0 / 4065.7 |
| Pair 1 rerun | 4081.8 / 1181.0 | 4082.1 / 4073.4 |

The rerun used the same frozen artifacts and cache declaration in main-then-candidate
order. The original pair remains in the range and table.
The rerun passed the framework’s single-pair check; it did not establish a faster
complete Conversation.
The three useful-prior cases separately started with a rendered Conversation, then
selected the absent-record target.
Candidate kept useful content throughout in all three, with zero observed blank frames.
Main recorded 364, 365 and 364. The initial neutral selection prompt in the first set
gives no evidence about prior-content retention.
[Public prior PR](https://github.com/jlevy/metabrowser/pull/298)

## Iterations and limits

Candidate01 was rejected.
Its description improved, but full completion regressed in all five paired runs by
368–929 ms. Candidate02 restored regular poll cadence after acknowledgement.
Its five-pair trial retained a 3075.4 / 4066.2 ms full-completion outlier, then recorded
4082.8 / 3066.6 ms in the documented rerun.
Candidate03 adds the selected GraphQL core measured in exp-049.

These samples establish early description on one missing-record path and continuity for
one prior-PR transition.
Poll cadence and provider variation limit the full-completion conclusion.
The generic journeys have their own gates.

## Final review checks

After the late Files renderer and empty Pulls pane fixes, three repeat pairs reached the
description in 1.01–1.24 s against 3.07–4.08 s. One full Conversation pair went from
3.07 s to 4.07 s; its prescribed rerun went from 4.09 s to 3.06 s. The separate prior-PR
transition showed the replacement description at 1.26 s with zero blank frames.
The generic directory journeys passed the unchanged performance gate.

A later loading-only correction keeps the gray blocks visible while the first POST is
outstanding. A held-request session and an installed-wheel browser click confirmed that
the blocks replace the empty Pulls prompt and give way to the selected title and
description. The correction adds no requests; those checks make no timing claim.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
