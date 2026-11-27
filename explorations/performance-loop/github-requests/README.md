# GitHub Requests While Browsing

What one scripted session of browsing pull requests asks of GitHub, measured with the
request report (`GET /api/plugin/github/gh-requests`,
[The Request Report](../../../docs/project/architecture/arch-github-pull-requests.md#the-request-report)).
These are records: they keep the date, the build, and what was run, and are not
rewritten when the code moves on.

The session is [`github_browsing.py`](../github_browsing.py): open the Pulls tab and at
once its top pull request, which nothing has read, while the catalog and the status scan
still read; let that page ask again; switch to the closed pull requests and open one;
come back to the open list, which names its top rows for the prefetch, and scroll; open
a prefetched pull request; and revisit the first.
Its docstring has the steps and the dwells between them.
`tests/test_github_browsing_benchmark.py` runs the same session against the in-process
stand-in, whose `gh` answers each kind of read after the time run 4 below took, and
holds its report to the invariants the
[merge readiness plan](../../../docs/project/specs/active/plan-2026-11-26-pull-request-merge-readiness.md#phase-3-github-request-performance)
asks of browsing.

## 2026-11-27: This Repository, Live

**What ran.** Four runs of the session against `https://github.com/jlevy/metabrowser`,
each against a server started with an empty cache and event log:

- **The build:** `metab 0.1.0.dev629+ed6be6d (ed6be6d, dirty)`, the lane commit of
  `mb-6719` with the uncommitted changes of the commit that adds this record, which
  added the report’s `order`, `repeats`, slot spans, and per-call waits.
- **gh 2.97.0**, signed in, reaching `api.github.com` directly.
- **The host:** a Linux 6.18 x86_64 container with 4 CPUs, load average 0.2 to 1.8, with
  other agents’ tests running beside it.
- **The repository:** Git here is 2.43.0, below Metabrowser’s acquisition floor, so the
  server could not acquire a mirror.
  It served a blobless clone of the repository at `9d99df3edaa4` as a folder, whose
  Pulls tab reads the repository through `gh` as a mirror’s does; its store was not
  acquired, and the session asks for no comparison.
- **The runs:** run 1 at 01:02 UTC and run 2 at 01:09 ran earlier orders of the session
  while it was being written, and run 1’s step windows stopped at each step’s end, so
  calls that ended during a dwell are missing from its steps.
  Run 3, at 01:29, ran the session as committed, but its step windows overlapped by the
  second each step began in, which the report’s whole-second `since` and `until` cannot
  part, so a call that ended in that second counts in both steps.
  Run 4, from 01:37:13 to 01:38:15 UTC, begins each step on a whole second
  (`Driver.begin`), so its steps part its calls exactly; the numbers below are its own.
  The four took 70, 51, 56, and 61 seconds.

The samples are each run’s report over the session and over each step, with the event
log’s directory replaced by `$STATE`: [run 1](2026-11-27-jlevy-metabrowser-run1.json),
[run 2](2026-11-27-jlevy-metabrowser-run2.json),
[run 3](2026-11-27-jlevy-metabrowser-run3.json), and
[run 4](2026-11-27-jlevy-metabrowser-run4.json).

**Run 4, the session.** 43 `gh` calls, 26 REST and 17 GraphQL, of which 32 were answered
`200` and 11 `304`. They spent 15 `core` calls and 17 GraphQL points.
`gh` took 357 ms at the median and 731 ms at the 95th percentile, and 2,167 ms at the
longest, the status scan’s first page.
At most 4 calls ran at once, from at most 2 spans, both holding one of the coordinator’s
two network slots. Four calls repeated an identical one answered under four seconds
before, all of them the account check.

| Lane | Calls | `core` | GraphQL points | Answered `304` | Waits for a slot |
| --- | --- | --- | --- | --- | --- |
| visible | 24 | 11 | 6 | 7 | 1, 176 ms |
| attended | 2 | 0 | 0 | 2 | none |
| prefetch | 6 | 4 | 0 | 2 | none |
| background | 11 | 0 | 11 | 0 | 2, 1,831 ms in all |

No call of a less urgent lane started while a more urgent call asked before it waited
for a slot (`order`’s `overtook` is 0 for every pair); two prefetch calls and one
background call started while a visible call asked before them ran.
The backfill’s wait of 1.6 s was behind the top row’s Fetch, asked before it.

| Step | Calls | `core` | Points | What it read |
| --- | --- | --- | --- | --- |
| open the Pulls tab | 4 | 1 | 3 | the account, the open filter’s first page, the first screen’s cores, and the first backfill page |
| open the top row at once | 16 | 4 | 10 | #911 with Fetch and its status, the status scan, and most of the backfill |
| its page asks again | 2 | 1 | 1 | #911’s probe, its first answer paid, and the last backfill page |
| switch to closed and open the first | 8 | 5 | 1 | the list’s probe, its first answer paid, and #910 with Fetch |
| come back to the open list and scroll | 8 | 4 | 1 | the list’s probe, the second screen’s cores, and the prefetch of #908 (#911 was current) |
| open the second | 3 | 0 | 1 | #908’s status, and the list behind it, `304` |
| revisit the first | 2 | 0 | 0 | #911’s probe and the list behind it, both `304` |

The median time of each kind of read, which the in-process benchmark gives its stand-in:

| Read | Calls | Median | Least | Most |
| --- | --- | --- | --- | --- |
| account check | 8 | 216 ms | 191 ms | 288 ms |
| list probe | 4 | 342 ms | 332 ms | 357 ms |
| a pull request’s probe | 2 | 295 ms | 268 ms | 321 ms |
| the pull | 3 | 368 ms | 314 ms | 369 ms |
| a record’s part | 9 | 282 ms | 226 ms | 399 ms |
| status read | 3 | 669 ms | 562 ms | 777 ms |
| cores batch | 2 | 655 ms | 637 ms | 673 ms |
| catalog page | 10 | 645 ms | 408 ms | 731 ms |
| status scan, first page | 1 | 2,167 ms |  |  |
| status scan, a later page | 1 | 479 ms |  |  |

Run 4 probed no pull request’s checks pages; run 2’s four took 403 ms at the median,
which the benchmark uses.
The account’s own counters fell from 4,981 to 4,966 `core` and from 4,962 to 4,960
GraphQL points over run 4, other clients included.

**The in-process session**, against the stand-in with those latencies and a catalog of
402 pull requests, a backfill of five pages, makes 43 calls and spends 15 `core` and 16
GraphQL points, the 31 its bound prices; its top row’s Fetch waits for a slot, as run
4’s did. `tests/golden/github-browsing-benchmark.txt` pins its calls by lane and by
burst.

## Findings for the Tuning

For the plan’s tuning (`mb-3i1s`), each to be measured before and after with the report
and the benchmark; none is changed here.

- **Every pull request’s job checks the account twice**, before and after its reads: 4
  of run 4’s 43 calls, 6 of run 2’s 56, and 4 in process, repeat an account check
  answered under four seconds earlier.
  Each is a free `304` but takes about a fifth of a second of a two-second record read.
  The plan already lists fewer account checks per refresh.
- **The lanes are first come, first served.** Nothing overtook, but nothing is preferred
  either: run 4’s top-row Fetch waited 176 ms for a slot behind a backfill page and the
  status scan’s first page, run 3’s 220 ms, and in run 2 the closed filter’s first
  catalog page waited 1.67 s. The scan’s first page is the slowest read GitHub answers,
  2.2 to 2.7 s in all four runs against about half a second for a later page, and it
  holds a slot that long; its own measurements beside `SCAN_ROWS` put most of a page’s
  time in `mergeStateStatus`. Ordering the lanes, or keeping a slot for visible work,
  would let a reader’s Fetch go first.
- **A filter switch reads the reader’s whole prefix as visible work.** In run 2 the
  closed filter was asked while the catalog’s job was still running, and the job read
  the closed prefix to the tab’s `DISPLAY_ROWS` target, five pages and about three
  seconds, though the reader looks at one screen.
- **A status scan’s re-read made the next page read its status.** In run 1 a settle
  re-read of the scan was followed, on the revisit of the first pull request, by a
  status read of its own (one GraphQL point), as a scan’s status of a head, which lists
  no checks, asks a page to do (`listing_missing`); runs 3 and 4’s revisits were all
  `304`s. Worth confirming against the scan that keeps a page’s listed checks.

## Deferred for the Owner

The plan asks for the same session against a large public repository as well, and for
`mb-mg37`’s hour of real browsing, which `AUTOMATIC_CORE_PER_HOUR` and
`SPECULATIVE_CORE_PER_HOUR` still wait on.
Neither was run here: both are left for the owner, and `github_browsing.py live` is the
driver for the first.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
