---
title: The prefetched libraries wait for idle
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-001
  title: The prefetched libraries wait for idle
  date: "2026-08-21"
  hypotheses:
    - H1
  subject:
    corpus: devtools/bench_serving.py build_corpus
    corpus_files: 100000
    corpus_dirs: 972
    host_system: Darwin 25.5.0
    browser: Chromium
    cold: true
    viewport: "0x0"
  method:
    runs_per_condition: 3
    interleaved: false
    control: the chain started by the DOMContentLoaded handler
    candidate: the chain scheduled on DOMContentLoaded and started by requestIdleCallback with a 2000 ms timeout
    record: explorations/results/runs.jsonl
  results:
    - metric: load_ms
      control_median: 3883
      candidate_median: 750
      control_range: [3278, 4819]
      candidate_range: [426, 798]
      change_pct: -80.7
      overlapping: false
    - metric: first_row_ms
      control_median: 854
      candidate_median: 999
      control_range: [678, 1591]
      candidate_range: [690, 1106]
      change_pct: 17.0
      overlapping: true
    - metric: load_tree_ms
      control_median: 434
      candidate_median: 268
      control_range: [314, 721]
      candidate_range: [253, 327]
      change_pct: -38.2
      overlapping: true
  complexity:
    lines_changed: 30
    new_dependencies: []
    new_failure_modes:
      - "A main thread busy past the 2000 ms timeout highlights a source view late rather than on mount; the metabrowser:optional-asset-loaded re-enhance path covers it, and it was verified in a browser."
    notes: Two named constants and one scheduling wrapper in server.py. No new mechanism.
  verdict:
    decision: accepted
    primary_metric: first_row_ms
    reason: "Accepted against its own primary metric failing. first_row_ms did not move and its ranges overlap almost completely, so the part of H1 about competing with the tree render is unsupported at this corpus size. load_ms did move, on ranges that do not overlap, and the tier policy in docs/development.md already asked for idle. Kept on those two, and the prediction is recorded as failed rather than restated against load_ms."
    commit: c4f0085
---
# The prefetched libraries wait for idle

## Hypothesis

**H1.** highlight.js, its TOML grammar, and Mustache start loading from the
`DOMContentLoaded` handler, which is the same window in which the first `/api/tree`
fetch and the tree render run.
Two costs follow: they compete with the tree for the main thread and the connection
pool, and the `load` event cannot fire until the whole serial chain finishes.
Starting them on the first idle callback should remove both.

The metrics named before measuring were `load_ms` and `first_row_ms`. `first_row_ms` was
the primary one, because it is the measure a reader feels.

## What was tried

The chain still *schedules* on `DOMContentLoaded`; it now *starts* on the first
`requestIdleCallback`, with `PREFETCH_IDLE_TIMEOUT_MS` as the floor and a plain 200 ms
timer where `requestIdleCallback` is unavailable.

The floor is the part worth arguing about.
On a large tree the main thread is busy for seconds, so an unbounded idle wait could
defer highlighting indefinitely, and a source view that never highlights is worse than
one that highlights late.

## What the numbers said

Three cold runs per condition on the 100,000-file corpus, each on a fresh port and a
fresh server, so both the HTTP cache and the index started cold.

| metric | control | candidate |
| --- | --- | --- |
| `load_ms` | 3,883 (3,278–4,819) | **750 (426–798)** |
| `first_row_ms` | 854 (678–1,591) | 999 (690–1,106) |
| `load_tree_ms` | 434 (314–721) | 268 (253–327) |

**`load_ms` moved and the ranges are clear of each other.** In the control the load
event was waiting for the chain, which was itself queued behind the in-flight tree
requests.
Once the chain starts after `DOMContentLoaded`, it is no longer inside the load
event at all.

**`first_row_ms` did not move, and the point estimate moved the wrong way.** The two
ranges overlap almost completely.
At three runs this says nothing about direction, and the honest reading is that the
competition H1 predicted is either absent or smaller than the noise on this corpus.
`load_tree_ms` looks better in the candidate for the same reason and is equally
unsupported — its ranges overlap too.

The noise is worth stating plainly, because it sets the floor for every later round: a
cold `dcl_ms` on this corpus ranged from 152 ms to 1,176 ms with nothing changed.
Three runs is enough to see an 80% move and nowhere near enough to see a 15% one.

## Limitations

**These six runs were taken in a 0x0 browser pane.** That was discovered during exp-002,
and is why `probe.js` now records the viewport and `record` refuses a run without one.
Both conditions met the same collapsed pane, so the comparison between them stands; the
absolute numbers do not describe a layout any reader has.
The tree pages its rows against the nav scroller’s height, so a real 1280x900 pane
mounts 334 rows where these runs mounted 237.

Beyond that: one corpus, one machine, one browser, three runs.
The corpus is 972 directories wide and shallow apart from one branch, so it exercises
breadth rather than depth.
`load_ms` is also partly definitional here: moving work out of the load window
necessarily removes it from `loadEventEnd`, and the reason to care is that the browser
treats the page as still loading until then, not that 3.1 seconds of work disappeared.

## Verdict

**ACCEPTED, with its primary metric unmet.** The reader-facing measure did not move.
What justifies keeping the change is the `load_ms` result and the tier policy in
[docs/development.md](../../docs/development.md#asset-loading-tiers), which already
described this tier as fetched during idle while the code started it on
`DOMContentLoaded`.

Verified in a browser that a Python source view still renders `language-python hljs`:
the libraries arrive during idle and re-enhance what is on screen through
`metabrowser:optional-asset-loaded`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
