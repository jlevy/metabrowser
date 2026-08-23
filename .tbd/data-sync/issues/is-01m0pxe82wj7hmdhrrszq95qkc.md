---
type: is
id: is-01m0pxe82wj7hmdhrrszq95qkc
title: "Nav clicks read as dead during a large scan: a 12px chevron and a shared request queue"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-08-23T08:57:48.378Z
updated_at: 2026-08-23T08:57:48.378Z
---
Reported from real use on a 241,063-file tree (~/wrk/aisw/trading, 124,750 visible + 116,313 ignored, 5.15 GB, walk 73.7s): during the initial scan, clicking nav rows appears to do nothing. Initial load itself was fast, which is the perf work behaving.

WHAT IS NOT WRONG, established first because three separate probes said otherwise and all three were wrong. Expand and collapse WORK, during the scan and after it. A full pointer sequence on the chevron during scanning fetches `/api/tree?path=attic&depth=2` in 14ms and the children group goes from 1 child to 132, height 0px to auto. An element-level `.click()` does NOT trigger the handler -- it flips aria by another path and never opens the group -- so any measurement built on synthetic clicks reports a failure that is the probe's, not the app's. Calibrate the instrument against the settled case before trusting it on the scanning case.

TWO THINGS THAT ARE REAL.

1. THE CHEVRON IS A 12x12 PX TARGET. Measured from its bounding rect. The row is 288x24. A click a few pixels off the chevron lands on the row, whose `data-action` is `select-dir`: the folder gets selected and the main pane navigates, but nothing expands. Visually that reads as "nothing happened", and it is exactly what one of my own real mouse clicks did -- landed at (12,128), selected `attic`, left it collapsed. On a tree where rows are 24px tall this is easy to hit wrong repeatedly.

2. CONCURRENT REQUESTS QUEUE DURING THE SCAN. Sequentially, a subtree request during scanning is fast:

    /api/tree?path=docs&depth=2       10.9ms      during scan
    /api/tree?path=devops&depth=2     10.9ms
    /api/tree?path=scripts&depth=2    14.2ms

But when the client fires several at once -- which the prefetch sweep does -- one page-side capture showed four landing together at IDENTICAL times:

    /api/tree?path=attic&depth=2        14ms   (the one the click triggered)
    /api/tree?path=__pycache__&depth=2 837ms
    /api/tree?path=brainstorming&depth=2 837ms
    /api/tree?path=devops&depth=2      837ms
    /api/index/progress                837ms

Four identical figures is the signature of a queue draining as a batch, not of four slow requests. ~830ms of queueing against an 11ms service time. A click whose fetch lands behind that batch takes most of a second to show anything.

CAVEAT ON THAT SECOND POINT: one capture, four requests. The direction is clear and the magnitude is not established. Worth repeating under controlled concurrency before anyone sizes a fix to it.

EXPANSION IS LAZY, which is what makes the queueing visible. The children group holds a `tree-lazy-placeholder` spinner until `/api/tree?path=...` returns, so an expand is always a round trip. When that round trip is 14ms nobody notices; when it is behind an 830ms queue, the spinner is the whole experience.

WHAT TO INVESTIGATE. Whether the chevron's hit area can grow without stealing the row's select target -- padding on the toggle rather than a bigger glyph. And whether the prefetch sweep should yield to a user-initiated expand, since the sweep is speculative and the click is not; today they share one queue and the speculative work can be ahead of the real request.
