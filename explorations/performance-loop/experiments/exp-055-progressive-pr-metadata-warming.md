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
    corpus: Recorded public-fixture PR metadata, 24 rows, exact production Pulls controller.
    corpus_files: 1
    host_system: Darwin 25.5.0, Node 24.19.0
    browser: No browser in the controller diagnosis; browser comparison pending.
  method:
    runs_per_condition: 1
    record: exp-055-controller-samples.jsonl
    control: Reviewed a7d3c013 controller with no hidden detail preparation and one busy retry.
    candidate: Idle startup in both repository modes, viewport-wide priority, and one progressive catalog pass.
  results:
  - metric: hidden_prepared_rows
    control_median: 0
    candidate_median: 24
    overlapping: false
  verdict:
    decision: unresolved
    primary_metric: hidden_prepared_rows
    reason: Deterministic controller behavior is verified; paired browser latency and startup guards remain pending.
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

## Remaining Acceptance Evidence

The persistence layer must independently verify row and catalog identity, atomic
private-file writes, account/repository replacement, stale display, and cache-only reads
after a minute and a server restart.
The frontend uses settled batch receipts and stops source traversal on a failed or held
receipt. Selected work keeps the existing provider priority.

Before accepting a browser performance improvement, compare independently prepared
control and candidate caches in alternating visible-browser runs.
Measure initial Files readiness, first PR description after idle warmup, a row beyond
the first transport batch, an immediate click while warming is active, and a cached
description after more than a minute.
Record provider requests, decoded bytes, selected/full Conversation latency,
responsiveness and the unchanged startup gates.
Until those comparisons complete, the result is a verified scheduling correction with
browser performance acceptance open.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
