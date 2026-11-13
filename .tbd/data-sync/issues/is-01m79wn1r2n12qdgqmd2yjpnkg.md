---
type: is
id: is-01m79wn1r2n12qdgqmd2yjpnkg
title: "H89 follow-up: parallel loading with a preload cap or low fetch priority"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-11-ui-apparent-performance.md
labels: []
dependencies: []
parent_id: is-01m774q0ep0jq6vhb790rart0v
created_at: 2026-11-13T07:23:47.841Z
updated_at: 2026-11-13T07:23:47.841Z
---
Follow-up to H89 after exp-062 rejected it. Make the parallel loading pay off on a cold
load without delaying the first styled view. Two candidates, each a round of its own:
cap the preloads (only the next few scripts of a bundle are in flight at once), or start
them at low fetch priority (`fetchpriority="low"`) so the first view's KPress
stylesheets go first.

The code to start from is on the do-not-merge reference branch
claude/perf-delivery-h89-reference (cut from 14150b84): c0c293bd (the parallel loader),
640e008d (KPress loading moved to the sdk-views tier), and the H89 half of 66b66aa3
(B3 and B4 preload tidying). PR #372 reverted all three in c30ee25c, add7edac, and
8ce4a224.

exp-062's numbers, at d0fe9618 against 09903292. Four judged pairs per instrument,
landing,files journeys, harness 5031dc16 at scenario revision 4, one-minute load 12 or
less throughout:
- Levels to the last shell-tools script: 21 (19-23) -> 5 (5-5), pairs 0.217-0.263.
- Levels to the last KPress asset: 25 (25-28) -> 19.5 (19-20), pairs 0.679-0.80.
- Time to shell tools ready, cold Markdown landing: 357.8 (310.5-371.6) -> 324.5
  (302.8-353.6) ms. Ranges overlap; no detected difference.
- Cold Markdown painted ready, the guard: 311.0 (293.8-331.8) -> 362.3 (343.7-420.2)
  ms. Ranges apart, pairs 1.16-1.27, inside the 1.3x tolerance. Blank frames went
  13 -> 16.5 and placeholder frames 10 -> 13.5: wrong-way results.
- From the probe, the last shell-tools script ends at 238.1 -> 176.95 ms and the last
  KPress asset at 264.35 -> 304 ms (overlapping).

Two mechanisms fit the later styled view, and exp-062 did not separate them. One is the
14 parallel fetches holding the browser's connections while the KPress stylesheets
wait; the other is KPress loading starting later from the sdk-views tier. Take one
network waterfall of a cold landing per build before choosing a candidate.

The startup budget matters too. With 640e008d reverted, #372's head is 320 bytes under
the budget instead of 3,016. A candidate that moves KPress loading out of the eager SDK
again gets that headroom back.

Record: explorations/performance-loop/experiments/exp-062-parallel-shell-tools-and-kpress-loading.md
(on claude/perf-delivery). Not to be run yet.
