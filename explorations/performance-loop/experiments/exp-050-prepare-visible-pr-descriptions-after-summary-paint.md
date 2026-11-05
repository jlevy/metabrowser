---
title: Prepare Visible PR Descriptions After Summary Paint
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-050
  title: Prepare Visible PR Descriptions After Summary Paint
  date: '2026-11-04'
  hypotheses:
  - H81
  subject:
    corpus: Public jlevy/metabrowser at db52ec09, with independently copied held Git and catalog data and the selected full record absent.
    corpus_files: 1245
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0, CPython 3.14.7, Git 2.50.1, Node 24.19.0
    browser: Visible Google Chrome 152, with a fresh origin and profile per case.
    viewport: 1600x900
  method:
    runs_per_condition: 2
    interleaved: true
    control: Exact installed 0d1b132d, early description on selection with no visible background batch.
    candidate: Trial 03, one bounded visible batch after summaries paint and exact selected refresh afterward. Installed wheel and source hashes accompany each sample.
    record: exp-050-rejected-focused-samples.jsonl
  results:
  - metric: prepared_description_ms
    control_median: 1153.8
    candidate_median: 35.7
    control_range: [1048.8, 1258.7]
    candidate_range: [34.2, 37.2]
    overlapping: false
  - metric: immediate_full_conversation_ms
    control_median: 3070.1
    candidate_median: 4120.1
    control_range: [3068.6, 3071.6]
    candidate_range: [4069.3, 4170.9]
    overlapping: false
  verdict:
    decision: rejected
    primary_metric: prepared_description_ms
    reason: Both matched ready clicks passed 150 ms, but two immediate pairs exceeded the full-Conversation guard. The trial stopped with 15 of 30 captures; it was not eligible to ship.
---
`mb-oywk` registered one bounded batch for visible rows after summary paint.
The live provider probe in
[exp-048](exp-048-measure-provider-cost-of-preparing-visible-pr-core.md) left
descriptions out of the initial catalog.
This trial used a separate GraphQL batch, with no speculative discussion, checks, Git,
diff, or manifest. The full record still needed its own selected acquisition.

An initial pilot opened Pulls before the clock began.
Its apparent immediate hits are not timing evidence.
The corrected observer started with a painted README in Files, opened Pulls through
trusted input, and clocked dwell from the first visible target under All.
It tested immediate, 350 ms, and 2,000 ms clicks and observed actual readiness
independently of the planned wait.

A live prepend of PR #299 changed the cached list’s pagination generation while the
admitted PR summaries were unchanged.
Two trial 02 ready clicks missed because the old proof depended on pagination order.
Trial 03 used catalog identity and row validation for already admitted descriptions,
while new requests still needed the current generation.
The paired timing fixture then held the catalog with #299 already present; the
stale-list misses are retained separately.

| Matched case | Description control / trial (ms) | Full Conversation control / trial (ms) |
| --- | ---: | ---: |
| Ready 1 | 1,049 / 37 | 4,063 / 3,061 |
| Ready 2 | 1,259 / 34 | 3,063 / 3,063 |
| Immediate 1 | 1,200 / 1,073 | 3,072 / 4,171 |
| Immediate 2 | 1,176 / 1,532 | 3,069 / 4,069 |

Both immediate pairs saw the same visible rows and no ready description.
The only preparation attempt in each trial was refused as busy; no speculative provider
process was sampled.
Full records published 258 and 505 ms later, then missed the three-second poll by about
150 ms. Browser observation added the rest of the roughly one-second loss.
The data do not attribute the later publication to speculation.
Two losses still exceed the declared guard, so this candidate stopped without a rerun or
generic gate claim. Separately, the two ready cases sampled an unrelated batch while
selected work was still active.
That is a separate change to test, not an explanation for the immediate pairs.

The 34–37 ms prepared reads show the opportunity, not an accepted product result.
`mb-oywk` retains the preparation work; `mb-dmby` isolates the local time from
publication to paint.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
