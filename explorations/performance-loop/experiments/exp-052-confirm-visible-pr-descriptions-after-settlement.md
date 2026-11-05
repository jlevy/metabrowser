---
title: Confirm Visible PR Description Preparation After Settlement
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-052
  title: Confirm Visible PR Description Preparation After Settlement
  date: '2026-11-05'
  hypotheses:
  - H81
  subject:
    corpus: Public jlevy/metabrowser at db52ec09, with the same independently copied held Git and catalog inputs and an absent selected full record.
    corpus_files: 1245
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0, CPython 3.14.7, Git 2.50.1, Node 24.19.0
    browser: Visible Google Chrome 152, with a fresh origin and profile per case.
    viewport: 1600x900
  method:
    runs_per_condition: 5
    interleaved: true
    control: Exact final pin-safe H82 wheel from exp-051, with no visible preparation.
    candidate: The same settlement behavior plus one bounded visible description batch, indexed summary validation, and selected refresh priority.
    record: exp-052-focused-samples.jsonl
  results:
  - metric: ready_window_description_ms
    control_median: 1093.8
    candidate_median: 38.3
    control_range: [1054.2, 1224.9]
    candidate_range: [37.3, 40.0]
    overlapping: false
  verdict:
    decision: accepted
    primary_metric: ready_window_description_ms
    reason: Five prepared clicks passed 150 ms, the single local outlier cleared its prescribed rerun, and the unchanged hard responsiveness gate passed.
---
[Exp-050](exp-050-prepare-visible-pr-descriptions-after-summary-paint.md) remains
rejected. This round uses the final selected-refresh handoff from
[exp-051](exp-051-wake-selected-pr-cache-read-on-settlement.md) in both arms.
It tests one bounded description batch after the Pulls rows have painted.
A click can read a ready description, or fall back to the ordinary selected refresh.
The batch does no discussion, checks, Git, diff, or manifest work.

Before confirmation, we set a target of at least three actual prepared reads below 150
ms in the 2,000 ms cell, alongside separate checks for immediate and running clicks.
We measured five alternating pairs per cell, using trusted input from a painted Files
view with the same visible cohort and no programmed hover.
Dwell starts when the target row first becomes visible.
The observer records whether the result was ready independently of dwell.
We flag a local timing increase only when it exceeds both one 60 Hz frame and 10 percent
within a pair. The full record file’s modification time marks publication on the same
host clock as the click.
These measurements use independently copied cache fixtures, with the catalog and Git
inputs held and the selected full record absent.

| Planned dwell | Actual prepared trial reads | Description control / trial (ms) | Full Conversation control / trial (ms) |
| --- | ---: | ---: | ---: |
| 0 ms | 0 of 5 | 1,198–1,374 / 1,117–1,299 | 2,912–3,354 / 3,113–3,763 |
| 350 ms | 0 of 5 | 1,119–1,233 / 1,065–1,502 | 2,905–3,459 / 2,751–3,351 |
| 2,000 ms | 5 of 5 | 1,054–1,225 / 37–40 | 2,900–3,202 / 2,884–4,563 |

All immediate clicks used the ordinary path.
In the 350 ms cell, the target had been admitted for preparation but was not ready when
selected. The observer did not require a process sample to straddle the click; a held
session separately proves the batch is canceled and drained before the selected provider
starts. A second held test denies a new preparation while selected work has a spare
provider permit. No sampled speculative batch started between selected POST and full
publication in any trial.
The 50 ms process samples alone cannot rule out short work between samples.
No focused capture recorded a blank frame or a Long Task.

Two ready-window trials took 1.50 and 1.16 seconds longer to show the full Conversation.
Almost all of each difference came before publication.
Process samples show a longer Git HTTPS subprocess in the first case and longer GitHub
reviews in the second.
Both batches had already finished at least one second before the click.
The local handoff differed by 3.1 and 1.7 ms respectively.
This is evidence of a prepared-description gain; the total full record still depends on
the live provider and Git.
Three immediate or running pairs took 0.41–0.56 seconds longer end to end.
In each, the record published later and painted at least as soon after publication.
The first row painted in 76–95 ms on control and 74–86 ms on trial.

In the original matrix, the only local guard outlier was ready pair 1. Publication
landed after one cache wait had ended and about 58 ms before the next read started.
The original publication-to-paint measurement was 20.6 ms control and 81.8 ms trial; the
prescribed single rerun measured 39.5 ms and 32.5 ms with the same visible cohort.
The ledger retains both.

The final source review found that the initial random window ID required a secure
browser context.
A viewport session with only `getRandomValues` reproduced the failure on
the old code and passed with the replacement.
We rebuilt the wheel and confirmed the same path with three new ready pairs and one
immediate and running pair each.
The final ready descriptions painted in 36–43 ms versus 1,109–1,231 ms.
All three used prepared data.
Immediate and running clicks still used the selected refresh.
The one running local outlier came from the same interval between cache reads: 29.4 ms
control and 105.4 ms trial.
Its prescribed rerun measured 32.6 ms and 29.3 ms.
The original, rerun, and all full durations are retained.

The unchanged directory gate passed with three installed-wheel pairs before and three
after the token correction.
The prepared path earns its extra work because it avoids about a second of visible
waiting in the ready cases using one small request for at most eight visible rows, with
the same full-record authority and selected-work priority.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
