# Load-Time Explorations

A measured-improvement loop for how fast Metabrowser becomes usable.
Each round states a hypothesis before the change, measures it against the unchanged
build on the same corpus, and records the verdict — including when the answer is no.

The hypotheses this loop is working through are registered in
[the load-time plan](../docs/project/specs/active/plan-2026-08-21-load-time-performance.md#hypotheses).
The write-ups are in [experiments/](experiments/), one file per round.

This is deliberately smaller than
[`devtools/bench_serving.py`](../devtools/bench_serving.py), which measures serving and
belongs in `make verify`’s world.
Nothing here runs in CI. An exploration answers a question once; a benchmark defends an
answer forever, and only the second one earns a place in the release gate.

## The loop

```
1. HYPOTHESIS  Write down what you think is slow, why, and which metric would
               show it. Before the change. Register it in the plan.
2. MEASURE     The unchanged build, three or more cold runs.
3. CHANGE      The smallest diff that tests that one hypothesis.
4. MEASURE     The changed build, the same number of cold runs, same corpus.
5. DECIDE      The accept rule below. Write the verdict down either way.
6. RECORD      experiments/exp-NNN-<slug>.md, and update the hypothesis status.
```

Rejected rounds are worth as much as accepted ones and cost more to re-derive, so a
refuted hypothesis gets the same write-up as a confirmed one.

## Running a round

```shell
uv --config-file uv.toml run --frozen python explorations/run.py serve --files 100000
```

That restarts the server on a port nothing has used this session and prints its URL. The
port is the cold-cache mechanism: a port is part of the origin, so a fresh one gives
every static asset an empty HTTP cache without touching cache headers, and a fresh
process gives a scan that is still running.
Both are what a reader opening a large tree actually meets.

**Give the browser a real viewport first.** The tree pages its rows against the height
of the nav scroller, and the sweep that warms folders reads the same box, so a pane that
never got a size measures every layout-dependent number against nothing — while still
producing timings that look entirely reasonable.
This was learned by taking six runs in a 0x0 pane and only noticing when a rect came
back 8 px tall. 1280x900 is the size these numbers were taken at; `record` refuses
anything under 900x600 rather than letting it into the ledger.

**Check `document.visibilityState` too.** A hidden pane does not run idle callbacks on
any schedule — measured here at over 30 seconds for a single
`requestIdleCallback(fn, { timeout: 2000 })`, which is to say never.
Anything the shell defers to idle is unmeasurable in that state, and two runs of the
same code will disagree depending on how long each waited.
Request counts and transferred bytes do not care; scheduling does.
Record which one a finding depends on.

Load the URL, let the tree settle, evaluate [probe.js](probe.js) in the page, and record
what it prints:

```shell
uv --config-file uv.toml run --frozen python explorations/run.py record --label before --port 8600 --json '<paste>'
uv --config-file uv.toml run --frozen python explorations/run.py compare before after
```

`compare` prints each metric’s median with its range beside it.

### Why the browser half is driven by hand

Time to first row is a browser fact, and this repository has no committed browser
automation — adding one is a dependency decision under
[SUPPLY-CHAIN-SECURITY.md](../SUPPLY-CHAIN-SECURITY.md), not a detail of this harness.
So the loop is: the script owns the server, the corpus, the port, and the record; a
person or an agent with a browser owns the load and the paste.
That is enough to answer a question, and it adds nothing to the dependency surface.
Automating it is worth doing when the loop’s answers start needing to be defended
continuously rather than decided once — that is `mb-pwnw`, and it is where the page-load
phase of `bench_serving.py` belongs.

## What is measured

| Metric | What it is | Why |
| --- | --- | --- |
| `first_row_ms` | Wall clock until tree rows exist in the DOM | The measure that matters. Read from the app’s own `renderTreeNodes:root` span |
| `load_tree_ms` | The root `/api/tree` fetch plus its render | The largest single component of the above |
| `dcl_ms`, `load_ms` | Navigation timing | `load` reports a shell that painted, not a tree a reader can use |
| `last_resource_ms` | End of the last request the page made | The tail. A page can look finished and still be requesting |
| `subtree_requests` | `/api/tree?path=…` count | The folder-warming sweep, which is invisible in a page that looks idle |
| `tree_items`, `lazy_stubs`, `dom_nodes` | Rendered size | What row windowing has to bound |
| `transferred_kb`, `vendor_first_start_ms` | Payload and when the prefetched tier starts | The asset tiers |

`first_row_ms` is wall clock until a tree row exists.
Waiting for `load` reports a page that painted its shell, and waiting for network idle
reports a scan that finished; neither is when the reader can use the tree.

## The accept rule

A candidate is accepted when all of these hold:

- the median of the metric the hypothesis named moved in the predicted direction,
- the two ranges do not overlap, at three or more runs per condition,
- nothing else in the table moved the wrong way without being accounted for, and
- the complexity is worth it.

The first three are arithmetic.
The fourth is a judgment and gets written as one.

Two rules about honesty, both learned the expensive way:

**A median without its range is not a result.** These corpora are noisy — a cold run’s
`dcl_ms` has spanned 152 ms to 1,176 ms with nothing changed.
If the ranges overlap, the finding is “no detectable effect”, not “a small win”.

**The metric is named before the measurement.** Measuring on the metric a hypothesis
predicted, missing, and then finding another metric that passes is not an accept.
Say what moved and say the prediction failed.

## The corpus

`devtools/bench_serving.py`’s `build_corpus` builds it, and `run.py serve` builds it on
first use: 100,000 files across 972 directories, wide at the top and deep in one branch,
under `.bench/corpus-<files>/` (gitignored, about 625 MB at 100,000 files).

Absolute numbers move with hardware and page cache and do not carry between machines.
The relation is what carries, so every experiment records its own before alongside its
after rather than comparing against a number from another day.

**A fresh server is not a cold scan.** `serve` restarts the process, so the index starts
empty, but the operating system’s metadata cache does not.
After the corpus has been served a few times the walk finishes in well under a second,
and a page loaded then meets a settled index rather than a running one — which is a
different regime, and the difference is large: the folder-warming sweep took 32 requests
and stopped at 2.2 s against a settled index, and trickled one request per ~800 ms past
28 s against a running one.
Dropping the page cache on macOS needs root, so a run that did not do it says so rather
than implying a cold disk.
Record which regime a run met.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
