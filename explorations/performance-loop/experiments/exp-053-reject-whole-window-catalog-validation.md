---
title: Reject Whole-Window Validation After an Unrelated PR Update
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-053
  title: Reject Whole-Window Validation After an Unrelated PR Update
  date: '2026-11-05'
  hypotheses:
  - H81
  subject:
    corpus: Public jlevy/metabrowser at db52ec09, with independently copied held Git and catalog inputs and an absent selected full record.
    corpus_files: 1245
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0, CPython 3.14.7, Git 2.50.1, Node 24.19.0
    browser: Visible Google Chrome 152, with a fresh origin and profile per case.
    viewport: 1600x900
  method:
    runs_per_condition: 3
    interleaved: true
    control: The final installed H82-only wheel with no visible preparation.
    candidate: The installed H81 wheel with the first four review fixes and whole-window catalog validation.
    record: exp-053-focused-samples.jsonl
  results:
  - metric: actual_prepared_ready_reads
    control_median: 0
    candidate_median: 0
    control_range: [0, 0]
    candidate_range: [0, 0]
    overlapping: true
  verdict:
    decision: rejected
    primary_metric: actual_prepared_ready_reads
    reason: All three planned ready clicks fell back after an unrelated member changed, so the candidate missed its prepared-read target despite passing the directory gate.
---
The independent review added an explicit adoption guard, a cooldown for unchanged rows,
one retry for a busy viewport, and accurate Files changed loading text.
We kept the timing control, trusted input, and actual readiness classification from
[exp-052](exp-052-confirm-visible-pr-descriptions-after-settlement.md).
The new frozen fixture included the two newly opened performance PRs.
Both arms copied it independently and allowed the normal catalog refresh.

All three ready trial batches included #294 and #300. In each case the normal catalog
refresh advanced the generation before selection and changed only #300’s indexed
fingerprint among the eight visible rows.
The title and description of #294 remained exact.
The live refresh landed about 0.39–0.63 seconds before the click.
In the first two pairs, the original batch had completed before the change and the first
selected GET rejected its proof.
In the third, the original batch was still running at the change and the same
whole-window proof could not publish.

None of the ready cases used a prepared description.
The trial therefore failed its primary condition even though the ordinary descriptions
painted in 1,083–1,150 ms, the full record remained correct, and the unchanged directory
gate passed. Immediate and running selections still used ordinary acquisition.
One running local handoff exceeded its guard.
We retained it without repeating the pair because the variant already failed the
prepared-read condition.

The evidence points to the proof shared by all members of a batch.
Admission should still prove the exact requested visible cohort, and actual provider
results should still verify the viewer and repository.
After admission, an unchanged row should be able to keep its own proof when a sibling
changes. The next round tests that on the same stale fixture with live catalog refresh
still enabled.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
