---
title: Bind the Missing Selected PR Core to the GraphQL Viewer
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-049
  title: Bind the Missing Selected PR Core to the GraphQL Viewer
  date: '2026-11-04'
  hypotheses:
  - H80
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
    control: Installed candidate02 wheel, using REST core and an additional account check before early
      publication.
    candidate: Installed candidate03 wheel based on db52ec09. Wheel and source hashes in the sample record.
      GraphQL core carries its viewer in the response.
    record: exp-045-049-focused-samples.jsonl
  results:
  - metric: sampled_server_tree_rss_mib
    control_median: 352.8
    candidate_median: 312.7
    control_range:
    - 342.9
    - 355.2
    candidate_range:
    - 309.8
    - 329.8
    overlapping: false
  - metric: sampled_gh_peak
    control_median: 6
    candidate_median: 5
    control_range:
    - 6
    - 6
    candidate_range:
    - 5
    - 5
    overlapping: false
  - metric: selected_description_ms
    control_median: 1690.6
    candidate_median: 1147.7
    control_range:
    - 1373.6
    - 1923.1
    candidate_range:
    - 1131.6
    - 1706.3
    overlapping: true
  - metric: full_conversation_ms
    control_median: 4066.8
    candidate_median: 4056.5
    control_range:
    - 4064.6
    - 4081.1
    candidate_range:
    - 3055.9
    - 4074.3
    overlapping: true
  verdict:
    decision: accepted
    primary_metric: sampled_server_tree_rss_mib
    reason: Sampled process and memory peaks fell in all five pairs. Description and full-completion ranges
      overlap.
---
H80 was registered as `mb-npyj` before implementation.
The missing selected record takes core and viewer from one GraphQL response.
The viewer must match the initial reader before the early description becomes visible,
and the final account check still protects full publication.
Existing full records retain their REST ETag refresh path.
A first GraphQL core carries no REST validator.
The next REST refresh reads that core once to store its ETag; subsequent unchanged REST
refreshes can answer 304.

Six live API requests established complete normalized REST and GraphQL model equality
for an open draft, a closed unmerged draft, and a merged PR. The first two had real
potential merge SHAs.
The merged PR used its actual merge commit.
The live comparisons cover those three states.
[Closed unmerged PR](https://github.com/jlevy/metabrowser/pull/262),
[merged PR](https://github.com/jlevy/metabrowser/pull/294)

Five final pairs compared the installed REST-core candidate02 and GraphQL-core
candidate03 on the same absent-record selection.
The sampled server-tree RSS range fell from 342.9–355.2 MiB to 309.8–329.8 MiB. The
maximum count of simultaneous rows named `gh` in a 50 ms sample was six on each control
and five on each candidate.
This is a sampled concurrent peak.
Auth and core run sequentially outside the bounded five-part phase.

The description ranges overlap at 1,373.6–1,923.1 ms for REST and 1,131.6–1,706.3 ms for
GraphQL. Full Conversation held in these pairs, with overlapping ranges of
4,064.6–4,081.1 ms and 3,055.9–4,074.3 ms respectively.
The result supports lower observed resource use on this path.
It leaves a description latency improvement unproven.
Generic performance gates are separate.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
