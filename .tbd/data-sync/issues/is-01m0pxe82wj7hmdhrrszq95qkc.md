---
type: is
id: is-01m0pxe82wj7hmdhrrszq95qkc
title: Main thread blocked a third to a half of load on a 241k-file tree, in both builds
kind: bug
status: open
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-23T08:57:48.378Z
updated_at: 2026-08-23T17:23:48.629Z
---
Reported from real use on a 241,063-file tree (~/wrk/aisw/trading, 124,750 visible + 116,313 ignored, 5.15 GB): the page feels sluggish during the initial scan, and the chevron animation itself runs slow. That last detail is what identified the cause -- a CSS animation stutters when the MAIN THREAD is blocked, which rules out network latency and rules in long tasks.

MEASURED with a PerformanceObserver on longtask entries, observer installed ~6.5-7.4s into page life on both builds, run from page load until the index settled plus a grace period. Same tree, same machine, same browser.

                                0.6.0        main 66330af
    time to settle              ~442 s       ~117 s          3.8x faster
    long tasks                  325          59
    total main-thread blocked   153.3 s      71.3 s          2.2x less
    longest single task         7,940 ms     5,967 ms
    tasks over 1,000 ms         43           21
    tasks over 200 ms           119          50
    transferred                 618 KB       598 KB
    requests                    207          181
    blocked share of window     31.2%        53.9%           WORSE

NOT A REGRESSION. main is better on every absolute count: it settles 3.8x sooner, blocks the main thread for less than half as long in total, has a fifth as many long tasks, a shorter worst task, and half as many tasks over a second. Anyone comparing the two builds end to end gets a strictly better experience from main.

BUT THE DENSITY IS WORSE, and that is what the reporter is feeling. main does its remaining blocking work in a much shorter window, so while it lasts, the page is unresponsive a greater fraction of the time -- 53.9% against 31.2%. The ordeal is shorter and more intense. A user who does not run a stopwatch experiences the intensity, not the duration.

SO THE REAL FINDING IS A UX PROBLEM PRESENT IN BOTH BUILDS: on a tree this size the page spends between a third and a half of the loading period with the main thread blocked, in tasks that individually run to six and eight seconds. A six-second task is not jank, it is a freeze -- no animation, no click response, no paint. Twenty-one of them on main and forty-three on 0.6.0.

NOT EXPLAINED YET: what the long tasks are doing. It is not fetch volume -- 598 KB across 181 requests, and 0.6.0 moved slightly more in both. Candidates, in the order worth checking: rendering tree rows as `fs.change` events stream in from `/api/events` while the walker runs; recomputing the folder rollup or file-type breakdown per update; and the tally pass, since the worst tasks on main cluster at 84s, 91s, 95s, 106s and 110s, which is AFTER the walk completes. A profile with the Performance panel would name the function in one run; longtask entries only say that time was spent, not where.

TWO EARLIER THEORIES DISCARDED, both mine. A broken expand handler -- expansion works, and three probes that said otherwise were instrument faults (an element-level `.click()` never reaches the handler; `offsetParent !== null` reports a `visibility: hidden` group as visible). And the chevron hit area at 12x12 px -- that explained one of my own mis-aimed clicks and nothing about the report.

ONE MEASUREMENT WARNING for whoever picks this up. My first capture on main reported an 8,454 ms task and a 166% blocked share, which is nonsense: the observer was installed 53 s into page life with `buffered: true`, so it pulled in tasks from outside its own window. Install the observer immediately after navigation, record the install time, and report the window alongside the total -- a blocked percentage means nothing without the window it is a percentage of.
