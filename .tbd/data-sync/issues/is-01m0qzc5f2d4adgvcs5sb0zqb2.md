---
type: is
id: is-01m0qzc5f2d4adgvcs5sb0zqb2
title: "Responsiveness regressed against v0.6.0: earlier paint bought with a blocked thread"
kind: bug
status: closed
priority: 0
version: 5
labels: []
dependencies: []
parent_id: is-01m0r191gatek6ffx1e50wmgr8
child_order_hints:
  - is-01m0r4pm8rxaq5jnefyxnkymtj
created_at: 2026-08-23T18:50:51.745Z
updated_at: 2026-08-23T21:34:08.407Z
closed_at: 2026-08-23T21:34:08.406Z
close_reason: Retracted the hidden 55.3% capture, documented the valid visible evidence, fixed exact-removal semantics, and made visible responsiveness a hard performance-loop gate. The final visible 241,063-file candidate run completed with no profiler warning at the default 500 ms threshold, and the diagnostic 200 ms run had no Long Task or LoAF at or above 200 ms.
---
The perf campaign traded responsiveness for earlier first paint, and nobody measured the side it gave up.

REPORTED FROM USE, both builds, same 241,063-file tree:

  v0.6.0    slower to paint the nav, no file counts for several seconds -- and once
            the nav renders, THE UI IS RESPONSIVE while it finishes crawling.
  main      paints sooner, and is seriously unresponsive for the whole crawl.

MEASURED on main in a visible browser: main thread blocked 55.3% of a 107 s window, worst block 13,353 ms, 21 blocks over 200 ms; interaction latency 32 ms median, 3,144 ms at p95, 13,480 ms at worst. Half the clicks answer instantly and the worst hangs for thirteen seconds, which is why a median hides it completely.

WHY IT HAPPENED, and it is not an accident of implementation. The campaign's primary metric was first_row_ms, driven from 1,473 ms to 276 ms over ten rounds. Painting rows early means patching them live as the walk discovers files, so the main thread now does continuous work across the entire crawl where 0.6.0 did one render at the end. Earlier paint and continuous patching are the same decision.

THE LOOP PREDICTED THIS TWICE AND MEASURED IT NEITHER TIME:

  H56 -- "first_row_ms rewards painting *something* early and says nothing about how
          many states follow it." Open.
  H49 -- "the four unmeasured regimes hide regressions the cold-load metric cannot see:
          INTERACTION LATENCY, churn recovery, resident size, warm reopen." Open, P0.

Interaction latency is the first regime H49 names, and it is the one that regressed. The hypotheses were right, were registered, and were never turned into a measurement -- which is the actual process failure here, larger than any single change.

WHAT THIS MEANS FOR exp-011. That round concluded "no regressions against v0.6.0" and is corrected: accepted on the server half, contradicted on the browser half. Its own scope section said it measured only the server; that limitation turned out to be exactly where the regression lived, so it now reads as a finding rather than a caveat.

WHAT NOT TO CONCLUDE. The server work is real and stands: index 30.0 s to 11.9 s, identical rows, files and bytes, lower memory. This is not an argument for reverting it. It is an argument that the front end has to stop doing unbounded synchronous work while the walk runs -- H58 -- and that a round is not done until interaction latency has been read alongside first paint.

NEXT, in order. One clean visible-tab baseline of both builds on the same tree with metabrowserPerf.responsiveness(), so the comparison is measured rather than reported. Then the attribution the new freeze warning produces, naming the span that owns the thirteen seconds. Only then a fix.

## Notes

PR #73 review R1 (Blocker): exp-011 labels the 55.3%/13.4s capture visible while the active plan and source bead say the same capture was ever hidden and void. Re-run both builds visibly on one corpus and correct every summary.
