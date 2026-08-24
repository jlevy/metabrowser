---
title: Backend volume stops controlling browser responsiveness
softschema:
  contract: metabrowser.loadtime:Experiment/v1
  schema: experiment.schema.yaml
  envelope: experiment
  status: enforced
experiment:
  id: exp-014
  title: Backend volume stops controlling browser responsiveness
  date: "2026-08-23"
  hypotheses:
    - H9
    - H10
    - H11
    - H51
    - H57
    - H58
  subject:
    corpus: ten project-shaped trees cloned from the locked development installs
    corpus_files: 111590
    corpus_dirs: 6520
    host_system: Darwin 25.5.0
    browser: headed Chrome driven through the DevTools Protocol
    viewport: "1600x900"
    cold: true
  method:
    runs_per_condition: 4 browser and 5 backend
    interleaved: true
    control: globally installed v0.6.0 at tag v0.6.0
    candidate: installed wheel from PR head bf7771b
    record: harness-14 browser records and devtools/compare_builds.py output summarized below
  results:
    - metric: backend_first_row_s
      control_median: 2.647
      candidate_median: 1.107
      control_range: [2.626, 2.992]
      candidate_range: [1.105, 1.181]
      change_pct: -58.2
      overlapping: false
    - metric: backend_index_done_s
      control_median: 25.378
      candidate_median: 11.348
      control_range: [25.327, 28.016]
      candidate_range: [10.819, 11.651]
      change_pct: -55.3
      overlapping: false
    - metric: backend_peak_rss_mb
      control_median: 183.0
      candidate_median: 176.3
      control_range: [180.2, 184.0]
      candidate_range: [175.7, 176.4]
      change_pct: -3.7
      overlapping: false
    - metric: browser_inventory_delivery_work_pct
      control_median: 11.0
      candidate_median: 0.4
      control_range: [9.5, 12.0]
      candidate_range: [0.3, 0.4]
      change_pct: -96.4
      overlapping: false
    - metric: browser_inventory_delivery_max_ms
      control_median: 7
      candidate_median: 1
      control_range: [6, 7]
      candidate_range: [1, 2]
      change_pct: -85.7
      overlapping: false
    - metric: browser_startup_script_requests
      control_median: 75
      candidate_median: 22
      control_range: [75, 75]
      candidate_range: [22, 22]
      change_pct: -70.7
      overlapping: false
    - metric: browser_startup_script_transfer_kb
      control_median: 340
      candidate_median: 154
      control_range: [340, 340]
      candidate_range: [154, 154]
      change_pct: -54.7
      overlapping: false
    - metric: browser_transferred_kb
      control_median: 518
      candidate_median: 454
      control_range: [515, 519]
      candidate_range: [447, 460]
      change_pct: -12.4
      overlapping: false
    - metric: browser_fcp_ms
      control_median: 114
      candidate_median: 146
      control_range: [96, 116]
      candidate_range: [124, 172]
      change_pct: 28.1
      overlapping: false
    - metric: browser_first_row_ms
      control_median: 177
      candidate_median: 200
      control_range: [173, 188]
      candidate_range: [143, 235]
      change_pct: 13.0
      overlapping: true
  complexity:
    new_dependencies: []
    new_failure_modes:
      - deferred assets can miss an already-open stream event and leave a feature incomplete
      - a preload is reported with a link initiator and can be omitted from scripts or double-counted as CSS
      - accidental human input can contaminate an automated interaction run unless exact counts are checked
      - an append-only cold-origin ledger eventually outlives a narrow fixed port range
    notes: >-
      The product separates exact file removals from subtree removals, reconciles the
      standing tree, defers noncritical assets, preserves deferred catalog readiness,
      prioritizes the first tree request, and cooperatively yields inventory work.
      The reusable harness adds continuous trusted input, exact input accounting,
      application-boundary snapshots, startup attribution, readiness and final-data
      gates, retained-heap ordering, preload-aware resource classification, and a
      process-lifetime port allocator. No dependency or compatibility layer was added.
  verdict:
    decision: accepted
    primary_metric: hard responsiveness and correctness gates during progressive loading
    reason: >-
      The candidate passes every hard gate in every admissible final run while applying
      the same inventory volume in one-thirtieth of the browser work time. Backend rows,
      completion, and memory also improve with identical answers. This accepts the
      responsiveness fix, not a claim that every scalar is lower: cold FCP is 32 ms
      later and the local HTTP/1.1 startup queue remains named follow-up work.
---
# Backend volume stops controlling browser responsiveness

## Question

Did the performance work make the backend faster by moving enough synchronous work into
the browser to make the page sluggish, and does the final build keep UI responsiveness
independent of the inventory stream?

Yes to the first question in the regressed build, and yes to the second in the final
candidate. The failure was not a slow tree render or a single slow server response.
It was repeated catalog work whose cost grew with the complete file set, followed by an
asset and readiness path that the old performance loop did not measure.

## Root cause from first principles

An ignored file arriving from the initial inventory or the live stream is one exact file
removal from Quick File search.
The wire shape had combined that operation with filesystem subtree removal.
The browser therefore handled each ignored leaf by scanning the complete known-file
catalog for a matching path prefix.
A faster backend delivered more of those leaves sooner, multiplying
`O(events × catalog)` work on the UI thread and producing intermittent multi-second
stalls.

The repair preserves the operation at the boundary.
`catalog.change.remove_files` is exact and reaches `Map.delete`; a removal that may name
a directory retains the prefix-sweep path.
Bulk prefix removals sweep once per batch instead of once per path.
The fetched navigation tree now reconciles into keyed visible containers, and collapsed
descendants remain data in `subtreeCache` rather than hidden DOM. The inventory driver
also yields cooperatively between bounded entry groups, so a wide directory cannot
monopolize the server request loop.

The second part was startup work.
Plugin assets now load for the selected kind, and search, keyboard, Help, and Git tools
load only after the first usable tree.
The selected preview begins after the first tree request so its plugin assets cannot
take the tree’s HTTP connections.
Readiness remains a correctness property: a stream that opens before the deferred Quick
File bundle arrives still starts the catalog feed once both sides are ready.

## Why the earlier loop missed it

The previous loop emphasized first row, load, and a single interaction.
Each was capable of producing a good number while the page froze later:

- a single early click could precede the inventory burst;
- Long Tasks could miss an event storm made of individually short callbacks;
- backend completion could end a run before the browser consumed its final work;
- a deferred feature could fail to initialize and make the page appear unusually fast;
- forced garbage collection and adapter diagnostics could extend the product timing
  window; and
- script preloads could be omitted from JavaScript or charged to CSS because Resource
  Timing reports their initiator as `link`.

Harness 14 closes those holes.
It attaches at navigation, pulses trusted input from first usable state through settle,
sends a final input at the product boundary, and rejects any mismatch between generated
and observed input counts.
The standard profile freezes before forced collection and adapter fetches.
Inventory callbacks report count, item volume, maximum, total work, and window share;
the application adapter separately gates shell-tool readiness and authoritative catalog
completion. Startup resources are classified by requested path, so preloading changes
scheduling rather than category totals.

One baseline retry was rejected before recording because its controlled inputs covered
less than 80% of the loading window.
No user click entered the final evidence.
The append-only ledger keeps earlier harness versions for provenance, but none is pooled
into the harness-14 comparison.

## Exact build provenance

The browser control is the globally installed uv-tool console script, which reports
`metab 0.6.0`. The release predates the current recorder, so a temporary instrumented
copy replaces only its performance shim and connects that shim to the public namespace;
the release application and server sources remain exact.

The candidate is the wheel built from `bf7771b`, installed with the repository’s locked
dependencies in a fresh environment.
It reports `metab 0.6.1.dev65+bf7771b`. Browser runs used a visible 1600×900 headed
Chrome window, a fresh process and origin, and two pairs in each order.

## Browser result

Every candidate run is admissible and passes every hard responsiveness and correctness
gate. The release also happens not to enter its intermittent multi-second Long Task
pattern in these four final runs; earlier exact-release records reached 4.7–5.5 seconds,
which is why the final conclusion uses the direct sustained-work measure rather than a
lucky zero.

| measure | v0.6.0 median (range) | candidate median (range) | result |
| --- | ---: | ---: | --- |
| inventory callback maximum | 7 ms (6–7) | **1 ms (1–2)** | bounded slices |
| inventory work total | 1,684 ms (1,670–1,704) | **52 ms (48–57)** | 32× less UI work |
| inventory work share | 11% (9.5–12) | **0.4% (0.3–0.4)** | hard gate passes |
| trusted-input coverage | 84% (81.5–95.1) | **97% (97.0–97.5)** | later work exercised |
| startup scripts | 75 | **22** | 71% fewer |
| startup JavaScript | 340 KB | **154 KB** | 55% less |
| all requests | 124 (120–126) | **98 (96–101)** | 21% fewer |
| all transfer | 518 KB (515–519) | **454 KB (447–460)** | 12% less |
| stylesheet transfer | 80 KB | **73 KB** | 9% less |
| largest contentful paint | 212 ms (208–216) | **146 ms (124–172)** | 31% earlier |
| whole-tree builds | 1 | 1 | no regression |
| fetch errors and in-flight fetches | 0 | 0 | equivalent |
| final catalog incomplete | 0 | 0 | equivalent |

The first-row ranges overlap: 177 ms (173–188) for the release and 200 ms (143–235) for
the candidate. The candidate is not strictly lower on every cold-start scalar.
FCP is 146 ms (124–172), against 114 ms (96–116), and the first root request spends a 39
ms median on a 1 ms server handler because startup resources share the local HTTP/1.1
connection pool. A bounded diagnostic splits the slowest script’s 139 ms into 130 ms to
response start, 48.5 ms of server work within that wait, and 9 ms of download.
That remaining startup queue is H57 follow-up work; it is not main-thread sluggishness,
and it stays below the 200 ms first-paint budget.

Two visual roadmap targets also remain: the shipped tree frame is still short of its
settled height, and the tally summary moves 23 px.
They remain visible on every comparison and are not responsiveness gate failures.

## Backend result

The semantic comparator alternated five runs per build and refused timings until the
ordered rows and tallies matched.
They matched exactly, the corpus fingerprint did not move, and neither build reported an
error.

| measure | v0.6.0 median (range) | candidate median (range) | result |
| --- | ---: | ---: | --- |
| process to serving | 0.533 s (0.515–0.609) | 0.586 s (0.549–0.635) | no detected difference |
| first navigation row | 2.647 s (2.626–2.992) | **1.107 s (1.105–1.181)** | 2.4× faster |
| index complete | 25.378 s (25.327–28.016) | **11.348 s (10.819–11.651)** | 2.2× faster |
| peak RSS | 183.0 MB (180.2–184.0) | **176.3 MB (175.7–176.4)** | 3.7% lower |

The cooperative request-loop yield therefore preserves the backend gain while making the
scheduling invariant explicit.

## Reusable regression coverage

This round leaves the performance loop able to catch the regression immediately:

- navigation-time Long Tasks, Long Animation Frames, grouped Event Timing, and exact
  fetch outcomes;
- continuous trusted input with coverage and exact-count contamination checks;
- direct inventory-delivery maximum and sustained-work gates;
- shell-tool readiness, selected-renderer presence, and final catalog authority;
- startup request, transfer, tail, server, queue, and download attribution;
- forced-GC retained heap sampled after the product profile closes;
- preload-aware JavaScript and stylesheet accounting;
- immutable installed-build and corpus provenance, semantic backend equivalence, and an
  append-only cold-origin allocator that does not expire after 100 runs.

Another progressively loaded web application can reuse the recorder, policy, driver, and
comparison code. Only its adapter needs to define first usable state, completion,
correctness, and feature readiness.

## Verdict

**Accepted for the responsiveness regression and the pull request’s hard performance
gate.**

Backend event volume no longer controls browser responsiveness.
Every final candidate run stays at zero Long Tasks, keeps inventory work at 0.4% of the
window, reaches authoritative catalog completion, and preserves exact output while the
backend finishes more than twice as fast.

This is not a claim that every recorded scalar is lower.
Cold FCP remains 32 ms later than the installed release, and the frame and summary
roadmap targets remain open.
Those are named follow-ups rather than hidden inside the responsiveness win.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
