---
title: Keep Prepared Descriptions Through an Unrelated Catalog Update
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-054
  title: Keep Prepared Descriptions Through an Unrelated Catalog Update
  date: '2026-11-05'
  hypotheses:
  - H81
  - H83
  subject:
    corpus: Public jlevy/metabrowser at db52ec09, with independent copies of the same intentionally stale catalog and held Git inputs, and the selected full record absent.
    corpus_files: 1245
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0, CPython 3.14.7, Git 2.50.1, Node 24.19.0
    browser: Visible Google Chrome 152, fresh origin and profile for each case.
    viewport: 1600x900
  method:
    runs_per_condition: 5
    interleaved: true
    control: Exact final pin-safe H82 wheel, no visible preparation.
    candidate: Exact installed H81 wheel with reviewed bounded retries and per-row catalog validation after initial admission.
    record: exp-054-focused-samples.jsonl
  results:
  - metric: ready_window_description_ms
    control_median: 1133.8
    candidate_median: 38.1
    control_range: [1027.0, 1391.2]
    candidate_range: [33.6, 45.6]
    overlapping: false
  verdict:
    decision: accepted
    primary_metric: ready_window_description_ms
    reason: Five ready descriptions passed 150 ms, four survived a qualifying live sibling update, both local repeats cleared, and the unchanged directory gate passed.
---
[Exp-053](exp-053-reject-whole-window-catalog-validation.md) found that the batch was
admitted and fetched, but changing one catalog row discarded all its results.
H83 keeps exact cohort and generation validation at admission.
After GitHub verifies the viewer and repository, cache reads and selection use the
requested row’s indexed fingerprint with the same source, reader, repository, and epoch.
A held HTTP session changed a sibling during the batch; another changed it after
readiness. Both previously lost the stable preview.
In the corrected sessions the changed row was revoked, while the stable row remained
readable and could be adopted.
Its own later change still revoked it.

We reused the same deliberately stale frozen catalog in both arms and left normal live
refresh enabled.
Trusted input started in Files, opened Pulls, then selected the same row
with no programmed hover.
Five alternating pairs used a 2,000 ms dwell, with one pair each at 0 and 350 ms.
The planned dwell was distinct from actual readiness.
All 14 captures saw the same eight visible rows.

All five ready trials painted the verified description in 34–46 ms versus 1,027–1,391
ms. Four had a qualifying live update: the initial batch included #294 and #300, only
#300 changed, the catalog write preceded the first selected GET, and no second batch
prepared #294. In the remaining trial the update landed after the read.
It counts for the ready-click timing and not for the sibling-change claim.
The four live witnesses exercised validation after the first batch had settled.
The held test exercised a sibling change before publication.

Immediate and still-running clicks used ordinary selection.
The ready-window full Conversation took 2.70–3.20 s control and 2.82–3.13 s trial; this
experiment does not establish a faster full refresh.
No new speculative batch was sampled between the selected POST and full publication.
Held controls also verified that a selected acquisition takes priority and that a busy
viewport retries only once while it still owns that demand.
The 50 ms samples cannot by themselves exclude work shorter than a sample interval.

The first ready pair had an 82.2 to 102.6 ms first-row increase, before the preparation
request. The immediate pair’s publication-to-paint interval rose from 22.6 to 80.4 ms
when publication fell between waits.
Both were retained. Their single repeats measured 77.4 to 74.1 ms for first row and 32.3
to 33.5 ms for publication-to-paint.
The unchanged directory gate passed three installed pairs; startup request count and
transfer did not change.

The scoped gain is an immediately useful description once the small batch is ready,
including when a sibling updates.
The batch still leaves full discussion, checks, and Git acquisition to the selected
refresh.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
