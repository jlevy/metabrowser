---
title: The navigation tallies stop being recomputed per request
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-003
  title: The navigation tallies stop being recomputed per request
  date: "2026-08-22"
  hypotheses:
    - H8
    - H23
  subject:
    corpus: devtools/bench_serving.py build_corpus
    corpus_files: 300000
    corpus_dirs: 972
    host_system: Darwin 25.5.0
    browser: Chromium
    viewport: "1280x900"
    cold: true
  method:
    runs_per_condition: 3
    interleaved: false
    control: tallies memoized on rollup_revision, with the index snapshot taken on the event loop
    candidate: tallies served at a staleness bound of max(0.5 s, last pass cost), with the snapshot moved into the worker thread
    record: explorations/results/runs.jsonl
  results:
    - metric: srv_scanning_ms
      control_median: 638
      candidate_median: 375
      control_range: [621, 690]
      candidate_range: [342, 413]
      change_pct: -41.2
      overlapping: false
    - metric: srv_settled_ms
      control_median: 12
      candidate_median: 6
      control_range: [11, 12]
      candidate_range: [6, 6]
      change_pct: -50.0
      overlapping: false
    - metric: load_tree_ms
      control_median: 1816
      candidate_median: 1562
      control_range: [1816, 1816]
      candidate_range: [1562, 1562]
      change_pct: -14.0
      overlapping: true
  complexity:
    lines_changed: 152
    new_dependencies: []
    new_failure_modes:
      - "Nav filter counts can lag the index by up to one tally pass while a walk runs. The payload already carries tally_cache_status=scanning, so the client already presents them as provisional."
    notes: Two methods on the index and one branch in the tree route. A rejected third variant (request-triggered background refresh) was reverted; the code carries only the bound.
  verdict:
    decision: accepted
    primary_metric: srv_scanning_ms
    reason: "638 ms to 375 ms per root request during a walk and 12 ms to 6 ms settled, both on ranges that do not overlap, at n=3. Accepted for what it does -- every request after the first -- and explicitly not for first paint: load_tree_ms is the first request of a page load, its memo is cold by construction, and it did not move. The reader-facing fix for that is H20, not this."
---
# The navigation tallies stop being recomputed per request

## Hypothesis

**H23**, extracted from H8 by reading the code rather than measuring again.
`navigation_tallies` memoizes on `rollup_revision()`, and that revision advances on
every index write — about ninety times a second at the walker’s 256-entry emit batch.
So while a walk runs the memo can never hit, and every root `/api/tree` repeats a pass
whose own docstring prices it at roughly two seconds at 400,000 entries.

Predicted: serving the tallies at a bounded staleness during a scan brings the root
route from 837–1,567 ms down to near its settled 15 ms.

The metric named before measuring was `srv_scanning_ms` — the server’s own share of a
root `/api/tree`, from its `Server-Timing` header, while the walk runs.

## What the code read found that the hypothesis had not

A second O(N) cost, and the worse of the two.
The route took `inventory.entries(scope="all-known")` — a list copy of every entry,
300,000 of them — **on the event loop**, before the tally pass it fed even started.
It did that on every unfiltered root request, including the ones whose tallies were
about to be memoized away.
Only the filter path actually needed those entries in the handler.

So the change is two things: the bound, and moving the snapshot inside the worker thread
where the pass that needs it already runs.

Moving it naively broke something the suite already protected.
With a filter active the handler needs the entries itself, and two existing
source-scanning tests assert that a filtered root request snapshots the index exactly
once — both passes must describe the same index, and copying it twice is the cost the
invariant exists to prevent.
The lazy-snapshot version would have taken a second copy on precisely the request the
page makes first. The fix keeps both: unfiltered requests snapshot lazily inside the
thread, and a request that has already been forced to snapshot hands that one to the
tally pass.

## What was tried, in three passes

The first two are recorded because the loop is supposed to record what did not work, and
the second is only legible next to the first.

**A fixed half-second bound: 638 ms → 518 ms.** Real by the accept rule — the ranges do
not overlap — and far short of the prediction.
The reason is arithmetic: the nav polls index progress once a second, so a bound shorter
than the poll period can never be hit by a poller.
The constant was chosen from the client’s cadence and then set below it.

**A bound derived from the pass itself: 638 ms → 375 ms.** `max(0.5 s, last pass cost)`.
The server never spends much over half its time recomputing a number the client is
already told is provisional, and the policy scales with the tree instead of being tuned
for one size — the thing a constant cannot do, since the pass visits every entry.

**Request-triggered background refresh: rejected.** The idea was to fix the one case the
bound cannot: a page arriving mid-walk finds the memo absent or expired and pays the
full pass before its first row.
Measured at 368/380/409 ms against the bound’s 375/342/413 — ranges overlapping almost
entirely, so no detectable effect.
It could not have worked, and the measurement is what made that obvious: warming is
triggered *by a request*, so the first request still misses, and every request after the
first was already helped by the bound.
The code was reverted.
Warming driven by the walker rather than by a request is a different and untested
change.

## What the numbers said

Sampled from the server rather than the browser, because a browser cannot measure this
honestly: the pane takes seconds to start, so whether a page load lands inside the walk
or after it is luck, and a route that costs 1,500 ms scanning and 15 ms settled reports
whichever the luck picked.
`run.py probe-server` samples the route every second from the moment the socket answers
until the walk ends, then again once settled — thirteen scanning samples per run instead
of one draw.

| metric | control | candidate |
| --- | --- | --- |
| `srv_scanning_ms` | 638 (621–690) | **375 (342–413)** |
| `srv_settled_ms` | 12 (11–12) | **6 (6–6)** |
| `load_tree_ms` (browser) | 1,816 | 1,562 |

Settled halving is the snapshot removal on its own: with the memo hitting either way,
what is left is the list copy that no longer happens on the loop.

Sampling the same route four times a second instead of once shows the shape the median
hides: **7 ms median, with the occasional 1,451 ms**. That is the intended behavior
stated plainly — one pass per pass-duration, and every request between them free.

## The limitation, which is the finding

**First paint does not move, and cannot.** `load_tree_ms` is the first tree request of a
page load; its memo is cold by construction, so it pays the full pass no matter how
generous the bound. 1,816 ms against 1,562 ms, n=1 each, is not a result and is not
claimed as one.

This is worth being blunt about because it re-aims the plan.
H8 was the P0 on the strength of a 15-versus-1,567 ms split, and that split is real —
but it describes the *second* request onward.
The reader waiting on their first row was never going to be helped by making a cache hit
cheaper. Inlining the root’s first rows into the shell (H20) is the change that touches
them, and this experiment is the reason to run it next.

## Limitations

One corpus, one machine, n=3 per condition.
Every sample is `srv;dur` from the server’s own middleware, which measures entry to
response start and so excludes the client’s queueing — deliberately, since the question
was whether the handler is slow, but it means these are not end-to-end numbers.
The rejected warming variant was measured at the 1 s cadence only; a client burst at
page load is a regime none of the three variants was sampled in.

## Verdict

**ACCEPTED on `srv_scanning_ms`**, 638 ms → 375 ms, with settled 12 ms → 6 ms, both on
non-overlapping ranges.
Accepted for what it does — every request after the first, which on a page with a 1 s
progress poll and several tabs is most of them — and explicitly not for first paint,
which it does not touch.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
