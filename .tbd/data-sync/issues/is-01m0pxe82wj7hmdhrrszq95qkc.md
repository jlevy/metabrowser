---
type: is
id: is-01m0pxe82wj7hmdhrrszq95qkc
title: "Nav clicks feel dead during a large scan: requests queue behind the prefetch sweep"
kind: bug
status: open
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-08-23T08:57:48.378Z
updated_at: 2026-08-23T17:06:07.133Z
---
Reported from real use on a 241,063-file tree (~/wrk/aisw/trading, 124,750 visible + 116,313 ignored, 5.15 GB, walk 73.7s): during the initial scan, clicking nav rows appears to do nothing. Once the scan finished, expanding and collapsing worked normally. The initial load itself was fast, which is the perf work behaving.

TWO THEORIES DISCARDED, both mine, both wrong.

Not a broken expand handler. Expand and collapse work during the scan: a full pointer sequence on the chevron while scanning fetches `/api/tree?path=attic&depth=2` in 14ms and the children group goes from 1 child to 132, height 0px to auto. Three earlier probes said otherwise and all three were instrument faults -- an element-level `.click()` does not trigger the handler at all, and `offsetParent !== null` reports a `visibility: hidden` group as visible. Calibrate against the settled case before trusting a probe on the scanning case.

Not the chevron hit area. I measured it at 12x12 px and proposed that a near-miss lands on the row instead, selecting rather than expanding. The reporter uses it fine normally, so this explains one of my own mis-aimed clicks and nothing about the actual report. Discarded.

WHAT THE EVIDENCE STILL SUPPORTS: requests queue during the scan.

Issued one at a time, a subtree request while scanning is fast:

    /api/tree?path=docs&depth=2       10.9ms
    /api/tree?path=devops&depth=2     10.9ms
    /api/tree?path=scripts&depth=2    14.2ms
    /api/file?path=attic              20-50ms
    /api/rollup?path=attic&depth=1     8-40ms

But a page-side capture during an expand caught five landing at IDENTICAL times:

    /api/tree?path=attic&depth=2         14ms   (the click's own fetch, issued first)
    /api/tree?path=__pycache__&depth=2  837ms
    /api/tree?path=brainstorming&depth=2 837ms
    /api/tree?path=devops&depth=2       837ms
    /api/index/progress                 837ms

Five identical figures is a queue draining as a batch, not five slow requests: roughly 830ms of queueing against an ~11ms service time. Expansion is lazy -- the children group holds a `tree-lazy-placeholder` spinner until its fetch returns -- so every expand is a round trip, and a round trip behind that batch is most of a second of spinner.

Also observed, and not yet explained: page-side click handlers took 1.2-5.4s to return during the scan. That is main-thread time, not network, and it is the more likely source of a dead-feeling UI than the queue is. It was measured with the synthetic-click probe that turned out not to reach the handler, so the number may be measuring something else entirely. Re-measure before trusting it.

WHAT TO DO NEXT, in order. Reproduce the queueing under controlled concurrency -- N simultaneous subtree requests during a scan against the same N settled -- since one capture of five requests establishes a direction and not a magnitude. Then measure main-thread long tasks during the scan with the committed probe.js, which reports `long_task_ms_total`, rather than by timing a click handler. Only then decide whether the fix is on the server (the sweep and the click share one queue, and the sweep is speculative while the click is not) or in the client.
