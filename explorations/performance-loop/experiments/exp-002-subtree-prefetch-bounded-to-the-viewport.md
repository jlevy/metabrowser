---
title: The subtree sweep warms what is on screen
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-002
  title: The subtree sweep warms what is on screen
  date: "2026-08-21"
  hypotheses:
    - H2
    - H3
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
    control: candidates taken in DOM order, the first 32 lazy stubs in the tree pane
    candidate: candidates bounded to stubs whose folder row is on screen plus one screen of lookahead, with the sweep re-armed on scroll and on folder expansion
    record: explorations/performance-loop/results/runs.jsonl
  results:
    - metric: subtree_requests
      control_median: 32
      candidate_median: 0
      control_range: [32, 32]
      candidate_range: [0, 0]
      change_pct: -100.0
      overlapping: false
    - metric: transferred_kb
      control_median: 1566
      candidate_median: 517
      control_range: [1562, 1568]
      candidate_range: [516, 517]
      change_pct: -67.0
      overlapping: false
    - metric: first_row_ms
      control_median: 1200
      candidate_median: 1044
      control_range: [1043, 1660]
      candidate_range: [1017, 1449]
      change_pct: -13.0
      overlapping: true
    - metric: last_resource_ms
      control_median: 9398
      candidate_median: 9195
      control_range: [6834, 9975]
      candidate_range: [8795, 9361]
      change_pct: -2.2
      overlapping: true
  complexity:
    lines_changed: 46
    new_dependencies: []
    new_failure_modes:
      - "A layout read per stub per sweep. It runs inside the idle callback that already owns the work, and the sweep is capped at 32 candidates, so it is bounded by the cap rather than by the corpus."
      - "A zero-height scroller would reject every candidate and silently disable the prefetch. It falls back to the unbounded sweep instead, and the shim test pins that."
    notes: One predicate, one guard, and two places that re-arm the sweep. No new mechanism and no protocol change.
  verdict:
    decision: accepted
    primary_metric: subtree_requests
    reason: "32 requests and 1,049 KB removed per cold load, on ranges that do not overlap, for folders no reader could see. Time to first row did not measurably change and is not claimed. The property the prefetch exists for is preserved and was checked directly rather than inferred: expanding a folder warms exactly its ten newly visible children, and clicking one of those costs no fetch and paints in 93 ms."
---
# The subtree sweep warms what is on screen

## Hypothesis

**H2.** The sweep that warms collapsed folders takes the first 32 lazy stubs in DOM
order. Its own comment says those are “exactly the folders a reader can open next”, but
on a wide tree they are not: the root render of a 300,000-file corpus mounts **121 stubs
with no folder expanded**, so every one of them belongs to a folder that is at least two
clicks away. Bounding candidates to the rows actually on screen should remove those
requests without costing the instant expansion the sweep exists for.

The metric named before measuring was `subtree_requests`.

**H3**, the diagnostic that had to come first: an earlier observation showed the sweep
issuing one request per ~800 ms for 28 seconds, which does not follow from three
concurrent lanes over a 32-path sweep.
No policy change should land on top of a mechanism nobody understands.

## What was tried

H3 first, by instrumenting `prefetchPendingSubtrees` to record paths per sweep.
Then one predicate — `isNearNavViewport` — plus two places that re-arm the sweep: the
nav scroller’s `scroll` event, and `setFolderExpanded`.

The predicate has to test two different things, and only one of them is scrolling.
A collapsed branch clips its children with `overflow: hidden` rather than removing them,
so those rows keep full-height boxes stacked at the branch’s own position.
A rect test alone reads them as on screen — the first version of this change did exactly
that, and it took a debug dump showing `top00/mid01` and `top01/mid00` both at `top: 24`
to see it.

## What the numbers said

Three cold runs per condition, 1280x900, fresh port and fresh server each.

| metric | control | candidate |
| --- | --- | --- |
| `subtree_requests` | 32 (32–32) | **0 (0–0)** |
| `transferred_kb` | 1,566 (1,562–1,568) | **517 (516–517)** |
| `first_row_ms` | 1,200 (1,043–1,660) | 1,044 (1,017–1,449) |
| `last_resource_ms` | 9,398 (6,834–9,975) | 9,195 (8,795–9,361) |

**A megabyte, for folders nobody could see.** The two request metrics are decisive and
their ranges do not touch.
`first_row_ms` and `last_resource_ms` both look better and neither is claimed: their
ranges overlap heavily.

Then the check that matters more than any of them, because a prefetch that warms nothing
is not an improvement.
Expanding `top00` warmed exactly `top00/mid00` through `top00/mid09` — the ten rows that
expansion put on screen, and nothing else.
Clicking `top00/mid00` immediately after issued **no further request** and painted its
rows in **93 ms**.

### H3, and what a fresh server is not

H3 does not resolve, and the reason is worth more than the answer would have been.

Instrumented, the sweep does exactly what it says: **one sweep, 32 paths, all 32
requests issued inside 545–690 ms.** That held against a settled index and against a
scan with 12.9 seconds left to run, on both the current build and the one before the
prefetch-tier change.
The one-per-800-ms trickle did not reproduce in any of them.

The original observation is not withdrawn — it was recorded, with timestamps — but it
was taken when the corpus had not been served for a while and its walk took about 29
seconds, against 2.7 seconds for the same corpus once the operating system’s metadata
cache was warm. That is a different regime, and reaching it needs a cold page cache,
which needs root on macOS. So: **a fresh server is not a cold scan**, and the loop’s
README now says which regime a run met.

The bound landed anyway, because H2 does not depend on H3. Whatever the sweep’s cadence,
32 requests for folders two clicks away are 32 requests too many.

### The browser pane was hidden, which broke idle

Halfway through, expanding a folder stopped warming anything.
`document.visibilityState` was `"hidden"` for the whole session, and in that state a
single `requestIdleCallback(fn, { timeout: 2000 })` did not fire inside 30 seconds.

The sweep ran on one of those.
So the first version of this change made the prefetch depend on a callback the browser
was free to withhold, and two runs disagreed about whether expanding a folder warmed it
— the difference being how long each happened to wait.

The fix is a design correction rather than a workaround, and it would be right in a
visible tab too. A reader who has just opened a folder has said where they are; warming
its children is no longer speculation about *which* folder, only about the next click.
That earns `SUBTREE_PREFETCH_AFTER_EXPAND_MS`, a 50 ms timer, instead of an idle
callback. The speculative sweeps — first load, scrolling — still wait for idle, which is
what idle is for.

With the timer, in the same hidden pane, expanding a folder warms its ten children in
about 1.2 s and the click after that costs no fetch and paints in 75-77 ms, twice.

This also retires the last theory about H3’s trickle.
A hidden pane cannot be assumed to run idle callbacks on any schedule, so a sweep
observed dripping one request per ~800 ms was probably never measuring the sweep at all.

## Limitations

One corpus shape — 972 directories, wide and shallow apart from one branch — one
machine, one browser, three runs.
Every stub in this corpus is inside a collapsed branch, so the candidate condition
measures the floor rather than the steady state; a tree whose top level is expanded by
default would warm rows on load and is not covered here.
The lookahead of one screen is a judgment, not a measurement: nothing was tried against
two screens or half of one.

**Every run here was taken in a hidden browser pane**, and this environment offers no
way to make it visible.
Request counts do not depend on visibility and are trusted; anything about *when* a
speculative sweep fires does not survive the change of regime and is not claimed.
The scroll-triggered sweep is what that leaves unverified: it is idle-scheduled, and
idle is the thing that does not work here.

## Verdict

**ACCEPTED on `subtree_requests`,** with `transferred_kb` corroborating and no timing
claim made.
The change removes work that was never for the reader, and the expansion path
that justifies having a prefetch at all was verified rather than assumed.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
