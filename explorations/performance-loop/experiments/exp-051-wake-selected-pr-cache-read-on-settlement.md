---
title: Wake a Selected PR Cache Read When Its Refresh Settles
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-051
  title: Wake a Selected PR Cache Read When Its Refresh Settles
  date: '2026-11-04'
  hypotheses:
  - H82
  subject:
    corpus: Public jlevy/metabrowser at db52ec09, with independently copied held Git and catalog data and the selected full record absent.
    corpus_files: 1245
    host_cpu: Apple M1 Pro, 10 cores
    host_system: Darwin 25.5.0, CPython 3.14.7, Git 2.50.1, Node 24.19.0
    browser: Visible Google Chrome 152, with a fresh origin and profile per case.
    viewport: 1600x900
  method:
    runs_per_condition: 3
    interleaved: true
    control: Exact installed 0d1b132d wheel with the one-second pending-record poll.
    candidate: Final pin-safe H82 wheel based on 0d1b132d. A selected cache read can wait for the refresh already in progress.
    record: exp-051-focused-samples.jsonl
  results:
  - metric: publication_to_full_conversation_paint_ms
    control_median: 283.2
    candidate_median: 28.3
    control_range: [73.2, 852.1]
    candidate_range: [26.0, 29.1]
    overlapping: false
  verdict:
    decision: accepted
    primary_metric: publication_to_full_conversation_paint_ms
    reason: All three final pairs reduced the measured time after publication, the held request and pin controls passed, and the unchanged directory gate passed.
---
In [exp-050](exp-050-prepare-visible-pr-descriptions-after-summary-paint.md), two
selected refreshes published their full record about 150 ms after the three-second poll.
The browser waited for its next poll even though the record was already there.
`mb-dmby` registered H82 to test that local delay separately from provider and Git time.

A held HTTP session reproduced the old response returning before publication.
The candidate waits up to 900 ms for the matching current preview to settle or be
revoked. The route still reads from cache, and ordinary and duplicate reads remain
immediate. The browserless session holds the GET across a timer boundary and checks that
its next fast read stays anchored to the previous request’s start.
A real local pin switch reproduced an old claimed request reading the new revision; the
final build rechecks that claim and uses the standard `409 pin_changed` response.

Trusted clicks opened #294 after a rendered README and the same visible Pulls cohort.
The full record was absent, with Git objects and catalog rows held.
We used the full record file’s modification time as a proxy for its atomic publication,
calibrated to the same host clock as the click.
The readiness marker required the correct full Conversation to paint.
The samples retain click-to-description and click-to-full times alongside publication
and paint. No speculative provider work ran in this experiment.

| Variant | Paired runs | Publication-to-paint control (ms) | Publication-to-paint trial (ms) |
| --- | ---: | ---: | ---: |
| Before pin review | 5 | 166–965 | 26–105 |
| Final pin-safe wheel | 3 | 73–852 | 26–29 |

Both exact variants passed the existing directory performance gates in separate
comparisons. All eight focused pairs improved the publication-to-paint interval.
One final trial had a Git HTTPS subprocess sampled for about 37 seconds.
Its full Conversation took 39.6 seconds, then painted 28 ms after publication.
That run remains in the record.
This experiment establishes the local handoff improvement; it does not establish faster
provider work or faster total completion across repositories.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
