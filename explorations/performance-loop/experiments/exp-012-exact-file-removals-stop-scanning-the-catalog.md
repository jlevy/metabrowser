---
title: Exact file removals stop scanning the catalog
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-012
  title: Exact file removals stop scanning the catalog
  date: "2026-08-23"
  hypotheses:
    - H58
  subject:
    corpus: a real working tree, counted by the inventory completion log
    corpus_files: 241063
    host_system: Darwin 25.5.0
    browser: Chromium in the visible in-app browser
    viewport: "1600x900"
    cold: false
  method:
    runs_per_condition: 1
    interleaved: false
    control: PR head b6e1433
    candidate: b6e1433 plus exact-file catalog removals
    record: visible-browser console and server completion log, reproduced below
  results:
    - metric: long_tasks_over_500ms
      control_median: 3
      candidate_median: 0
      control_range: [3, 3]
      candidate_range: [0, 0]
      change_pct: -100.0
      overlapping: false
  complexity:
    new_dependencies: []
    new_failure_modes:
      - catalog.change producers must distinguish an exact file eviction from a filesystem path whose descendants may also have been removed
    notes: >-
      The product change adds one internal event field and two constant-time Map
      deletion paths. Long Animation Frame attribution and bounded whole-window
      responsiveness counters remain as diagnostics. Tests fail if an exact
      eviction enumerates catalog keys.
  verdict:
    decision: accepted
    primary_metric: long_tasks_over_500ms
    reason: >-
      A visible settled reload of the PR head produced three main-thread blocks
      over 500 ms, with a 6,393 ms maximum. The candidate produced none; a
      stricter 200 ms diagnostic also stayed silent through a complete cold scan
      of 241,063 files. Attribution and a key-enumeration test identify the same
      mechanism: exact ignored-file updates were routed through a catalog-wide
      subtree scan. Splitting exact file removals from subtree removals changes
      that path from one full scan per file to one Map deletion per file.
---
# Exact file removals stop scanning the catalog

## Question

The server-side performance work is real: exp-011 measures the current build indexing
the project corpus in 11.9 seconds where `0.6.0` takes 30.0. Why, then, does the faster
build feel less responsive while it loads a large tree?

Start at the boundary.
Network I/O and the server’s inventory walk do not execute on the browser’s main thread.
They can make content arrive late or quickly, but they cannot directly prevent a click
or paint. A frozen page therefore means synchronous browser work whose cost grows with
either the data already held or the events arriving.

The first record attached to H58 did not establish that work.
It was captured in a hidden tab but described as visible, so its 55.3% blocked share and
13.4-second maximum are discarded.
This round starts again in a visible tab and keeps attribution beside the timing.

## Attribution

A settled reload of the unchanged PR head produced three long tasks: approximately 0.8,
6.4, and 1.0 seconds.
Chromium’s Long Animation Frame entries attributed the largest frame to the promise
callback parsing and applying a tree response.
The new span around `knownFileCatalog.observeLazyTree` narrowed it further: applying a
19.8 KB response containing 25 top-level nodes took 6,678 ms.
Parsing and layout were not the cost.

The catalog stores file leaves in a `Map` keyed by full path.
When a prefetched tree reports a gitignored file, that file must not appear in Quick
File. The client knew the row was one file, but called the directory-removal helper
anyway. That helper must scan every catalog key because a filesystem removal may name a
directory and therefore remove descendants.
On this tree, each ignored leaf caused another scan across roughly 241,000 known files.

Changing that passive observation to an exact `Map.delete` removed the settled-reload
freeze, but it did not finish the diagnosis.
A fresh scan still produced progressively longer animation frames, from 742 ms and 1.5
seconds to a run of 1.2–4.6-second frames.
Those frames contained dozens of `EventSource.oncatalog.change` callbacks, each growing
from roughly 18 to 68 ms as the catalog filled and delivered back to back.

The same semantic loss existed on the wire.
The server combined two different facts in `catalog.change.removes`:

- A filesystem path disappeared.
  It may be a directory, so descendants must go too.
- One upsert says a known file is gitignored.
  Only that exact file becomes ineligible.

The browser had no way to recover the distinction and correctly chose the expensive,
subtree-safe interpretation for both.
The faster inventory producer made the latent mistake more visible by delivering many
exact removals during the crawl, and viewport subtree warming exercised the same path
earlier.

## Change

`catalog.change` now carries exact ignored-file evictions in `remove_files` and retains
filesystem subtree removals in `removes`. The browser applies each exact eviction with
`Map.delete`; only a path that might be a directory enters the prefix sweep.
The existing exception remains: an ignored file the reader explicitly navigated to stays
findable.

The same distinction applies at the passive-tree seam.
An entry whose wire type is `file` is removed exactly and never reaches the subtree
helper.

The behavioral test replaces `Map` with a tracking subclass and fails if either exact
path calls `keys()`. Server tests assert that ignored upserts and filesystem removals
land in different wire fields, and the browser test asserts both eviction and the
explicit-navigation exception.

## Result

Primary comparison, one visible settled reload per condition on the same tree:

| measure | PR head | exact-removal candidate |
| --- | ---: | ---: |
| tasks at least 500 ms | 3 | **0** |
| longest such task | 6,393 ms | **none** |
| stricter 200 ms diagnostic | not enabled | **none** |

The sample count is one, so this is not a distribution claim.
It is enough to falsify the former multi-second failure mode because the effect is
orders of magnitude above timing noise, Chromium names the callback, the measured span
names the catalog operation, and the key-enumeration test reproduces its complexity
without a clock.

The candidate then ran cold on a fresh origin while the server indexed all 241,063
files.
The tab remained visible, the inventory completed in 90.1 seconds, and neither the
Long Task observer nor the Long Animation Frame observer reported an entry at or above
the temporarily lowered 200 ms threshold.
A server request took 2.8 seconds during that run; the page still did not freeze, which
is the transport-independence H58 asks for.

A final cold handoff run repeated the same 241,063-file scan with the completed profiler
and budget framework in place.
It settled in 57.0 seconds, accepted a trusted filter interaction during the crawl and
two more after settle, reached the full file count with no pending loading state, and
emitted no 500 ms freeze diagnostic.

`0.6.0` is useful context, not the control for the fix.
Its first twenty seconds can look responsive because it spends longer before the catalog
work arrives. Once settled, one visible reload produced 23 tasks of at least 500 ms,
55,833 ms total, a 16,151 ms maximum, and eight tasks over two seconds.
The reader’s report of a regression during the crawl was accurate, but the release was
not a responsiveness target to restore.
The candidate removes the underlying failure from both the progressive and bulk paths.

## Regression gate

This failure no longer depends on someone noticing the page and opening DevTools.
The profiler attaches with the document, maintains exact whole-window counts and maxima
outside its bounded detail rings, and records Long Animation Frame script attribution
beside Long Tasks and Event Timing.
The end-of-run probe reads that source instead of attaching late; its late-buffer view
has a different field name and cannot overwrite the valid totals.

`run.py record` now rejects a browser record that was hidden, attached late, never
interacted with, or captured before the application settled.
It retains a run that crosses a hard budget for diagnosis but exits nonzero immediately.
`run.py compare` requires three valid runs per condition and checks every candidate run,
not only the median, against the hard task, frame, interaction, and blocked-share
budgets in `performance-budgets.toml`. The unchanged PR head would therefore have failed
immediately on its first 6,393 ms task, even if its primary load-time metric improved.

The collector, adapter, policy, and orchestrator contract are documented in the
[Web Performance Framework](../../../docs/web-performance-framework.md), including the
cold-load, warm-reopen, progressive-load, churn-recovery, steady-interaction,
visual-stability, endurance, and backend-delivery loops another web application can
reuse.

## Verdict

**Accepted on `long_tasks_over_500ms`, 3 → 0.**

The root cause was neither backend latency nor DOM volume.
It was a contract that erased whether removal meant one known file or an unknown
filesystem subtree, turning exact updates into repeated index-wide browser work.
The fixed contract preserves that fact across the wire, and the visible cold run clears
H58’s no-task-over-200-ms target on the tree that reproduced the regression.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
