---
type: is
id: is-01m0hfmknkz8znnb2m9gm4x8d4
title: "[task] Browser-side measurement: request consolidation and ETag behavior"
kind: task
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-08-21T06:20:24.616Z
updated_at: 2026-08-21T06:43:36.079Z
closed_at: 2026-08-21T06:43:36.078Z
close_reason: null
---
The server-side harness (mb-l049) measures what curl can see. It cannot see what the
browser does with those responses, and that is where two of PR #59's mechanisms actually
pay off. Both need to be observable from the client, not inferred from server logs.

What to show:

- **Requests that arrive together are consolidated.** Several panels on one folder, and
  several tabs on the same folder, ask for the same answer at the same time. Confirm
  they collapse to one aggregation rather than N. The server shares one in-flight build
  per validator; the browser side of that has to be visible as request count and timing,
  not assumed.
- **ETags are working.** Distinguish the three outcomes, because they are three
  different paths and only one of them is free: a 304 revalidation, a retained body
  served to a client that arrived without a validator, and a genuine rebuild. Report
  which of the three each request took.
- Refresh behavior during a crawl, where the validator moves constantly and every poll
  is a real aggregation, versus a settled index, where it should not be.

Use the browser's own instrumentation (the Resource Timing entries and the Server-Timing
header the routes already emit) so the numbers are the ones a reader would actually
experience, including transfer size and whether the response came from cache.

Report per query shape. The folder Overview asks for several distinct shapes at once,
and a shape that never coalesces is invisible in an aggregate count.

## Notes

Implemented as devtools/bench_browser_probe.js, printed by
`bench_serving.py --browser-probe`. Load it in the page and call
`await metabrowserBench.run({clients: 8})`.

It reads `Server-Timing: srv;dur=<ms>`, which every route already emits, because
request count cannot answer either question: N requests are always N requests on the
wire, and what distinguishes a shared computation from a repeated one is how much work
the server did.

Validated on a settled 400,000-file index.

Validators, per shape:
- /api/rollup, both the Overview and treemap shapes: ETag stable, revalidation returns
  304 with an empty body, 8ms against 20.3ms for the aggregating first request.
- /api/tree, both shapes: no ETag at all, reported as unsupported rather than as a
  passing result.

Consolidation, reported with a verdict rather than a bare ratio, because the ratio alone
misleads. Two different mechanisms make a repeat request cheap:

- While scanning, the validator moves on every write, so nothing is cacheable and
  single-flight is what collapses simultaneous clients.
- Once settled, the first request retains its encoded body and later ones are handed it.
  Each is already cheap, so the ratio tracks N and that is correct, not a failure.

An early version called the settled case a coalescing failure. Per-client cost is what
separates them, so the verdict now uses that, against the 50ms budget in the design
system, and takes into account whether the route has a validator at all.

That distinction is what surfaced the finding now recorded on mb-bb8v: the root
/api/tree request has neither a validator nor a shared build, so 8 tabs each paid
8,557ms, for 68,459ms of server work. The same probe against a subtree costs 9.9ms per
client, so it is the root request specifically.

Follow-on: the probe is loaded by hand today (served from the corpus, then eval'd). If
it gets used routinely, it should be delivered by the harness instead.
