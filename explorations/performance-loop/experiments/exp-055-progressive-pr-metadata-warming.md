---
title: Progressive PR Metadata Warming
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-055
  title: Progressive PR Metadata Warming
  date: '2026-11-07'
  hypotheses: [H84]
  subject:
    corpus: Public jlevy/metabrowser checkout at 8b7eabc8, independent copies of one 308-row catalog-only seed, selecting PR 310 (twelfth Open row).
    corpus_files: 1268
    host_system: Darwin 25.5.0, CPython 3.14.7, Node 24.19.0
    browser: Built-in Chromium via CUA; trusted locator input and driver-observed DOM visibility.
    viewport: 1600x900
  method:
    runs_per_condition: 6
    interleaved: true
    record: exp-055-browser-samples.jsonl
    control: Installed 0.11.1.dev1218+7c0188f4, independent catalog-only cache per trial.
    candidate: Combined 1b17c680 product source, same catalog seed, durable cores and progressive idle preparation.
  results:
  - metric: description_observed_driver_ms
    control_median: 1320.5
    candidate_median: 73
    control_range: [1123, 3357]
    candidate_range: [71, 80]
    overlapping: false
  - metric: files_ready_driver_ms_matched_pairs_2_to_6
    control_median: 106
    candidate_median: 116
    control_range: [101, 2701]
    candidate_range: [106, 2461]
    overlapping: true
  - metric: preview_section_removed_driver_ms_pairs_4_to_6
    control_median: 2912
    candidate_median: 3021
    control_range: [2893, 4963]
    candidate_range: [2924, 3044]
    overlapping: true
  verdict:
    decision: accepted
    primary_metric: description_observed_driver_ms
    reason: All six prepared descriptions became observable in 71-80 ms versus 1123-3357 ms; durable restart and scheduler checks pass. This accepts the scoped metadata-readiness improvement, not a paint, INP, full-Conversation speed, or universal startup claim.
---
The reader observed a one-to-two-second wait after selecting a PR. Three mechanisms can
make a prefetched description miss.

1. Checkout Files startup does not mount the Pulls controller.
   A hidden managed Pulls controller reads the catalog, but sends no description demand.
2. A visible demand receives only one delayed retry.
   If the shared provider permit is busy for longer than that, unchanged viewport demand
   never retries.
3. The previous prepared-core window retains only its current eight rows and expires
   after a minute. Later batches and server restart lose that useful metadata.

The existing provider measurement in
[exp-048](exp-048-measure-provider-cost-of-preparing-visible-pr-core.md) priced one
eight-core batch at 894–1,068 ms and about 36.9 KB decoded.
[Exp-054](exp-054-keep-prepared-descriptions-through-a-catalog-update.md) measured
already-ready descriptions at 34–46 ms.
Neither measurement establishes the latency of this implementation.

## Controller Evidence

Before changing the source, the production controller was driven with its recorded
catalog and a virtual provider permit becoming free at 3,000 ms.
Hidden startup sent no preparation request.
Visible demand asked at 0 and 1,000 ms, then abandoned admission.

The focused production session
[github-pr-prefetch-behavior.js](../../../tests/dom/github-pr-prefetch-behavior.js) pins
the new behavior through the existing CLI golden.
All 24 visible rows are queued, using three transport batches, and the remaining catalog
is traversed by its existing local cursor.
A separate case keeps the permit busy for 65,000 ms.
Demand is admitted at 91,000 ms after exponential backoff capped at the existing
30-second settled polling delay.
There is no attempt-count or freshness-window abandonment.

The session also covers cold catalog startup, a later scrolled cohort already held in
the metadata cache, reconnect after the first eight rows, source-wide pause on a setup
failure, and recovery without skipping the unsettled cursor.
A completed hidden pass retains no polling timer.
These are deterministic ownership and scheduling assertions.
Their virtual-clock durations are not browser click measurements.

The default/current filter’s already-held page is primed before the All cursor.
A fixture with twelve more-recent Closed rows verifies that older Open rows warm first,
followed by All without duplicate provider work.
A known rate hold keeps one reset wake for its unfinished pass, even when Files stays
selected. Browser suspension and disposal cancel that wake.

## Browser Evidence

Six alternating pairs used independent copies of one frozen catalog with no detailed or
lightweight PR records at trial start.
Both arms browsed the same checkout and target, PR #310, the twelfth Open row.
Files remained selected for at least ten seconds before opening Pulls.
A cache-only read classified the target before the trusted click; inter-tool time adds
to that planned dwell.
Every control had no full record or prepared core, and every candidate had a core with
no full record. The first three pairs were uninstrumented.
The last three used the same streaming GitHub CLI counter in both arms.

The driver clock spans the real locator click, exact target heading visibility, and a
visible description body.
It includes automation and DOM-polling overhead.
It is not the renderer’s DOM marker, a painted milestone, or INP. The
[browser samples](exp-055-browser-samples.jsonl) retain all twelve observations.

The description median fell from 1,320.5 to 73 ms, with ranges of 1,123-3,357 and 71-80
ms. This fixed target is beyond the original eight-row cohort.
Files readiness in the five matched pairs had medians of 106 and 116 ms, with
overlapping ranges of 101-2,701 and 106-2,461 ms.
Pair 1 used a reload in the control and a new-origin navigation in the candidate; its
unmatched startup observations remain in the record as diagnostics.
These driver timings do not establish a general startup improvement.

For the last three pairs, the preview’s Discussion heading disappeared only when the
full record replaced the preview.
The medians were 2,912 and 3,021 ms, with overlapping ranges.
All twelve local caches subsequently held the selected full record.
There is no claim of a faster complete Conversation.
An earlier loading-text disappearance proxy could pass before that text appeared; those
pair-3 diagnostics remain marked invalid and are not used for this comparison.
A stale driver closure also interrupted pair 3 before its candidate click.
Its disposable cache was reset from the original seed and the repeated sample is marked.

## Provider and Storage Cost

The [backend samples](exp-055-backend-samples.jsonl) count completed GitHub CLI API
subprocesses and their stdout bytes, including response headers.
They are not compressed wire bytes or exact upstream HTTP request counts; GitHub CLI can
retry within a process.
The collector made no provider request.

| Pair | Control API calls / stdout bytes | Candidate API calls / stdout bytes |
| --- | ---: | ---: |
| 4 | 10 / 251,336 | 18 / 778,347 |
| 5 | 10 / 251,336 | 16 / 460,359 |
| 6 | 10 / 251,336 | 22 / 973,214 |

The extra work was GraphQL metadata preparation.
Both arms made seven REST API calls in each instrumented trial.
Their observation windows and warmed coverage differ, so these totals are not
equal-duration rates.
Uninstrumented cost is unknown.

Each catalog held 308 summaries totaling 145,752 decoded JSON bytes in a 348,160-byte
SQLite file. At the post-trial observation, candidate caches held 49-264 lightweight
cores totaling 221,897-1,593,527 bytes.
Those footprints are not simultaneous warm-up measurements.
Every cache had exactly one full PR record, 22,209 bytes, for the selected PR. The
control’s zero durable cores says nothing about its RAM-only preparation.
Background cores hold metadata and descriptions, leaving discussion, checks, file lists,
and Git acquisition to the existing demand paths.

## Restart and Scope

After the candidate server stopped, a new managed-repository CLI process read unselected
PR #309 from the same cache.
Its core was 143.5 seconds old, no full record existed, and the read made zero GitHub
CLI calls. The focused CLI golden separately covers offline restart, later batches, and
changed source/reader identity.

This round accepts progressive metadata readiness for the observed target and the
production scheduler’s coverage and recovery behavior.
It does not establish universal instant navigation, a quiet-host performance result, or
painted readiness. Larger repositories and release-wide performance gates retain their
separate evidence and follow-ups.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
