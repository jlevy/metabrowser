---
type: is
id: is-01m0pxe82wj7hmdhrrszq95qkc
title: Main thread blocked 55% of the crawl, in blocks to 13 s, on a 241k-file tree
kind: bug
status: open
priority: 0
version: 5
labels: []
dependencies: []
created_at: 2026-08-23T08:57:48.378Z
updated_at: 2026-08-23T18:44:58.297Z
---
CONFIRMED in a visible browser on a 241,063-file tree. The page is blocked for more than half the crawl, in blocks up to thirteen seconds. It stays that way until the crawl finishes.

    long_task_max_ms          13,353        interaction_p50_ms         32
    long_task_ms_total        59,367        interaction_p95_ms      3,144
    window_ms                107,324        interaction_max_ms     13,480
    main_thread_blocked_pct     55.3        interactions            2,086
    long_tasks_over_200ms         21        long_task_max_ms_first_5s 1,776

THE MEDIAN IS FINE AND THE TAIL IS NOT, which is the whole shape of the complaint. Half of interactions answer in 32 ms and the worst takes thirteen and a half seconds. Nobody experiences a median; they experience the click that hung.

NOT THE NETWORK, and this refutes the connection-starvation reading this bead carried at P0. The client's own fetch instrumentation separates the server's share from the rest, and on loopback:

    /api/tree?path=earnings_predictions/tools&depth=2   server 14 ms   transit 13,456 ms
    /api/tree?path=explorations/trends-revenue-beta     server  7 ms   transit  4,794 ms
    /api/index/progress                                 server  0 ms   transit  2,849 ms

Transit cannot be thirteen seconds over loopback. The response had arrived and no callback could run, because the thread was blocked. Every inflated fetch duration in these logs is a SYMPTOM of the blocking, not a cause of it -- and an earlier version of this bead had that backwards.

ONE GENUINE SERVER-SIDE OUTLIER, worth separating from the rest:

    /api/tree?depth=0                                   server 2,240 ms  transit 186 ms

That is the tally channel, and it is expensive by design (exp-007).

A FEEDBACK PATH THAT MAKES THE TWO MEET, from the stack in the logs:

    fileStoreApplyChangeInner -> applyCellPatch -> updateRootAggregatePresentation
      -> scheduleRootSummaryRefresh -> fetch /api/tree?depth=0

applyCellPatch runs PER ENTRY inside a change batch, and it reaches a scheduler for the one request whose server cost is measured in seconds. Whether the schedule coalesces is the thing to read next; if it does not, a burst of file events queues repeated tally computations behind a walk that is already saturating a core.

ALSO PRESENT: failed requests. Several /api/file calls return status 0 with size -1 after 2.5-4.4 s, which is an abort or a transport error rather than a slow answer, and apiFile:json is recorded with threw: true. Worth understanding separately -- a failing click and a slow click look identical to a reader.

STILL MISSING, and it is now the only thing between here and a fix: which span owns the thirteen seconds. perf.js now warns on any block over 500 ms and lists the measured spans overlapping it, so the next session on a large tree produces that attribution without anyone watching for it. The prime suspect is fileStoreApplySnapshot, which loops every entry the server sends in one synchronous pass -- measured at 17-48 ms on small trees, unmeasured on 241,063 files.

METHOD NOTE. `ever_hidden` was true for this capture because the tab was backgrounded while copying the output, so the totals are not admissible as a clean baseline even though visibility_state read "visible" at the end. The interaction figures are still evidence: they were produced by real clicks the reporter made while watching. A clean baseline needs one uninterrupted visible run.
