# Web Performance Framework

**Status:** Built and in use: the recorder, the Metabrowser adapter, the budget policy,
and the orchestrator below gate every performance-loop comparison.
The recorder still carries the four Metabrowser specifics named under Purpose.

## Purpose

A performance change is useful only when the application stays correct and responsive
while the named metric improves.
This framework turns that rule into a browser record, an application adapter, a budget
policy, and a comparison loop, for web applications that load progressively, keep live
state, or keep working after the first paint.

Metabrowser is the reference integration.
The recorder makes no DOM assumptions, and the adapter adds the moments that make the
application usable, such as its first tree row and final inventory state.
The recorder is not yet application-neutral, though: `src/metabrowser/static/perf.js`
requires and publishes on `window.metabrowser`, gives `/api/plugin/diff/comparison`
requests with a `file` parameter their own concurrency class, attributes Long Animation
Frames only to resources under `/api/`, and reads server time from the `srv` entry of
`Server-Timing`. Another application changes those four points.

## The Four Layers

| Layer | Metabrowser implementation | Reusable responsibility |
| --- | --- | --- |
| Navigation-time recorder | `src/metabrowser/static/perf.js` | Attach before application work; retain bounded detail and exact aggregates for fetches, named spans, paint, layout stability, Long Tasks, Long Animation Frames, and Event Timing |
| Application adapter | `explorations/performance-loop/probe.js` | Add app milestones, visual states, completion, DOM size, and route attribution to the standard profile |
| Policy | `explorations/performance-loop/performance-budgets.toml` | Declare evidence requirements, hard gates, and improvement targets without embedding them in the collector |
| Orchestrator | `explorations/performance-loop/run.py`, `capture-browser.js`, and `devtools/web_performance.py` | Preserve build and corpus provenance, drive trusted Chrome input without another package, reject invalid records, compare repeated conditions, and make budget failure a nonzero result |

The recorder is `window.metabrowser.perf`. Application code contributes spans through
`measure(label, fn, metadata)` and `measureAsync()`. Labels name operations, never paths
or other unbounded values, so whole-window attribution stays bounded.

## Console Diagnostics

The recorder runs from before application work starts, so opening the console after a
problem keeps the beginning of the session:

- `metabrowser.perf.report()` prints the profile and slow-operation tables;
- `metabrowser.perf.responsiveness()` returns the main-thread and interaction summary;
- `metabrowser.perf.copy()` and `download()` copy or save the complete JSON profile;
- `metabrowser.perf.reset()` starts a new measurement window.

After a reset, keep the tab visible and interact before treating the result as
responsiveness evidence; the profile says when visibility or observer coverage makes it
invalid.

## Measurement Contract

Navigation-time profiles use the flat `web-performance-profile/v1` envelope.
The stateful transition recorder has its own versioned records, with trusted input, the
exact destination’s first useful frame, and per-region continuity and convergence.
See the
[transition scenario](../explorations/performance-loop/README.md#transition-navigation-scenario)
for its evidence checks and cache regimes.

### Evidence Before Metrics

The loop refuses a record unless it establishes all of these, as the `[requirements]`
table of the policy declares:

- the navigation-time profiler produced the expected schema, and the tab stayed visible
  for the whole window;
- the required `PerformanceObserver` signals were supported;
- trusted input spans the progressive loading window, at least the policy’s minimum
  input count and coverage, and Event Timing was available; the count and span tell a
  fast input with no Event Timing entry from an untouched page;
- the application’s completion marker, readiness checks, and final-state checks passed,
  since a missed initialization event can make an incomplete application look fast;
- rendered main-panel errors and uncaught page exceptions, counted from navigation
  through export, are zero;
- application fetches are idle, so backend completion cannot end the profile while the
  browser is still consuming its result;
- the viewport clears the application’s floor;
- span labels, request-class attribution, and the Resource Timing buffer did not
  overflow; truncated totals are invalid, not low;
- the run carries corpus, build, dirty-tree, harness-version, and timestamp provenance.

A late observer is diagnostic only: its buffered entries cannot make a run valid or
overwrite navigation-time totals.
A missing or unsupported signal stays null or is named in `unsupported`; absence never
becomes a good zero.

### Metric Coverage

| Dimension | Standard fields | What they prevent |
| --- | --- | --- |
| Loading | `ttfb_ms`, `response_download_ms`, `dom_interactive_ms`, `dcl_ms`, `load_ms`, `fcp_ms`, `lcp_ms`, startup script count and transfer, and startup script and render-blocking stylesheet attribution split into response wait, server work, response tail, and download | Treating a fast shell, server response, or load event as a usable application, hiding an eager feature tier or cold import inside noisy paint timing, or guessing whether a slow asset waited on the application, server, or connection pool |
| Responsiveness | Long Task count, total, maximum, first-five-second maximum, tasks over budget, Total Blocking Time, blocked share, and application-delivery callback maximum and share | Hiding one multi-second freeze inside a total, or an event storm inside individually short callbacks |
| Frame attribution | Long Animation Frame count, maximum, blocking time, forced style and layout maximum, worst scripts and nearby resources | Knowing that the page froze without knowing which callback or rendering cost owned it |
| Interaction | Trusted-input count, first and last offset, span, loading-window coverage, plus grouped Event Timing interaction count, retained count, percentile scope, p50, p95, and exact maximum | Calling an untouched page responsive, counting one gesture’s several DOM events as several interactions, confusing no slow entry with no input, or reporting a bounded percentile as whole-session evidence |
| Visual stability | Navigation-time LCP and CLS’s maximum session window, plus adapter-defined movement and repaint counts | Improving first paint by assembling or moving the visible page afterwards, or reporting an all-session shift sum under the CLS name |
| Rendering and memory | Named-span counts, totals, maxima, first completion, `dom_nodes`, optional natural heap, and controlled post-profile-GC retained heap | Moving work into an unmeasured callback, growing the DOM with the corpus, or mistaking garbage-collection timing for retained-state growth |
| Network | Request count, in-flight count at capture, whole-window and per-request-class concurrency maxima, exact rejection, abort, 4xx, and 5xx totals, transfer by resource class, largest and slowest resources, endpoint timings, and `Server-Timing` | Ending a profile before client work settles, hiding a request storm because it eventually drains, or conflating server work with queueing, payload, and client processing |
| Backend and correctness | Scan completion, rendered main-panel error count, uncaught page-exception count, adapter-defined readiness and final-state checks, route samples, peak RSS, corpus fingerprint, and semantic API comparison | Buying browser speed with a missing feature, incomplete data, a renderer failure, a different answer, or cost moved behind the browser boundary |

The detail rings are bounded, while whole-window counts, totals, maxima, milestones, and
per-label aggregates are kept separately, so bounded retention does not erase the start
of a bad load. The record states how many samples were seen and retained and whether any
buffer overflowed.

### Standards and Lab Semantics

The fields follow the browser APIs.
[Event Timing](https://w3c.github.io/event-timing/) gives the events of one gesture the
same `interactionId`; the recorder groups on it and keeps the slowest duration, the unit
[Interaction to Next Paint](https://web.dev/articles/inp) is built on.
The hard gate uses the exact worst interaction rather than INP’s outlier rule, so a
reproducible freeze fails even when a long scripted journey could discard it.
[Long Tasks](https://w3c.github.io/longtasks/) give the portable blocking totals, and
[Long Animation Frames](https://w3c.github.io/long-animation-frames/) add Chromium’s
attribution where supported, staying null otherwise.
[Largest Contentful Paint](https://w3c.github.io/largest-contentful-paint/) and
[Layout Instability](https://wicg.github.io/layout-instability/) are observed from
navigation; CLS is the largest shift session window, not a sum over a long-lived page.
Where an engine lacks these observers, as the macOS app’s WebKit does,
[Idle Work](project/architecture/arch-browser-shell.md#idle-work) describes what the
recorder reports instead.

## Budgets and Targets

`performance-budgets.toml` holds every limit as a metric with a `maximum`, a `policy`,
and, where one exists, the measurement that set it.
This document names metrics; it does not restate their values.

- **Hard gates** (`policy = "gate"`) defend properties the application satisfies and
  must never trade away: the Long Task and Long Animation Frame blocking maxima,
  `interaction_max_ms`, `main_thread_blocked_pct`, the inventory-delivery callback
  gates, `first_row_ms`, the startup-script gates, render-blocking stylesheet server
  work, rejected fetches and 5xx responses, rendered and page errors,
  `shell_tools_missing`, `file_catalog_incomplete`, and
  `collapsed_diff_rows_materialized`, which fails a comparison whose folded rows are
  mounted though hidden.
- **Roadmap targets** (`policy = "target"`) are visible debts, such as raw Long
  Animation Frame duration, which Chromium can inflate with a document’s initial
  navigation gap, and aborts and 4xx responses until a scenario can declare them
  intentional. Every comparison reports them without blocking unrelated work; once one is
  reached and defended, change its policy to `gate` rather than moving the number into
  prose.

The startup-script ceilings bound what that tier costs, not which scripts are in it.
Tests hold membership: `tests/test_check_startup_scripts.py` keeps every on-demand
bundle out of the startup set, and `tests/test_plugin_extra_assets.py` keeps plugin
scripts out of the shell’s tags;
[Asset Loading Tiers](project/architecture/arch-browser-shell.md#asset-loading-tiers)
explains the tiers.

The comparison checks every candidate run against the gates, not the median, so one
freeze fails even if two clean runs would hide it.
Each condition needs `minimum_runs_per_condition` admissible runs before `compare`
succeeds, and the primary metric still needs a mechanism and non-overlapping ranges: the
budget gate is a constraint beside the experiment’s accept rule, not a substitute.

## The Performance Loops

No single page load covers every dimension.
Use the same record and policy in focused scenarios, with one control variable per
round.

| Loop | Scenario | Primary measures | Invariants carried beside them |
| --- | --- | --- | --- |
| Cold load | Fresh process and origin; load through application settle | TTFB, FCP, LCP, first usable state, tail | Responsiveness, CLS, repaint count, transfer, correctness |
| Warm reopen | Reuse the process, origin, persisted state, and browser cache; reopen the same subject | Time to usable and revalidated state, cache hits, transfer avoided | Stale-state labeling, background revalidation, responsiveness, final correctness |
| Progressive load | Large or streaming data source; interact while updates arrive | Long Task and frame maxima, Event Timing, blocked share | Completion, final state, dropped and resync signals |
| Churn and recovery | Burst updates, disconnect, reconnect, and force resynchronization | Convergence time, dropped events, resync count, update coalescing | Interaction latency during churn, final semantic equivalence, bounded caches |
| Steady interaction | Settled application; repeat one scripted user journey | p50, p95, maximum interaction latency; named handler spans | Correct outcome, DOM and heap before and after |
| Stateful navigation | Settled application; first-open, prepared, and revisited subjects with trusted input | Exact subject’s painted-ready time, blank and placeholder frames, changes to visible regions, and server and client phases | Continuous useful content, one active owner, bounded preparation, disposal, and heap |
| Large retained view | Open a bounded but DOM-heavy source such as a large comparison; collapse, expand, and replace | Projection spans, Long Tasks, DOM and heap before and after | Hidden content is not mounted, expansion yields, cancellation and final content are exact |
| Visual stability | Fixed viewport; capture shipped, intermediate, and final states | CLS, direct region movement, visual-state and repaint counts | First usable time and responsiveness do not regress |
| Endurance | Long-lived session with repeated navigation and updates | Heap slope, DOM ceiling, retained sample counts, listener and cache sizes | Interaction latency stays flat and attribution does not overflow |
| Backend delivery | Same corpus, with and without an attached client | Scan time, route wall and server time, RSS, payload | Browser hard gates and semantic response equivalence |
| Previous-release regression | Previous published artifact and candidate, installed and alternated on one unchanged corpus | Full metric vector from the affected loops, with ranges | Semantic equivalence, every candidate hard gate, immutable build and corpus provenance |

For a new metric, first name the user-visible failure, then choose the loop that can
make the field come out bad; a metric that can only report success is not a guard.

The previous-release row is a protocol across the other loops, not a score: at least the
cold-load, progressive-load, and backend-delivery scenarios, with repeated runs per
condition, full reports kept locally, normalized profiles in the evidence ledger, and a
committed result naming builds, ranges, limits, and the decision.
An overlapping range means no detected difference.
A candidate fails when any run crosses a hard gate, or when a repeatable wrong-way
metric lacks an accepted explanation.

Stateful navigation defines useful readiness rather than accepting the first paint after
input, since a prompt spinner can shorten Event Timing while the content arrives later.
Keep the prior surface observable through the transition, require the exact requested
subject at a painted boundary, and record blank or placeholder frames beside Event
Timing, with at least one cold asynchronous view in the journey.
Count subject-matching requests too: a selection must join or cancel matching prefetch
work, and a cached revisit must not reach the data route.
[Attributing Stateful-Navigation Delay](../explorations/performance-loop/README.md#attributing-stateful-navigation-delay)
gives the attribution sequence.

An older release may predate the recorder.
A measurement-only adapter may supply the current observers, provided the measured
product code stays exact, the release’s namespace and initialization order are
preserved, and the result documents the substitution.
Run an installed external build from a neutral working directory, not the candidate
checkout.

## Integrating Another Application

1. Initialize one console namespace, load the recorder before application work, and
   publish it on a stable property such as `app.perf`; replace the four Metabrowser
   specifics in `perf.js`. Size Resource Timing capacity above the largest measured
   scenario and keep the overflow check.
2. Wrap stable operations with `measure(label, fn, metadata)` or
   `measureAsync(label, fn, metadata)`, with finite labels and bounded metadata.
3. Write an adapter that reads the standard snapshot and adds the first usable state,
   completion marker, visible-region changes, correctness facts, and the boundary
   between shell startup and feature loading.
   Gate feature readiness and final data authority separately from quiescence, so a
   missed callback cannot pass as reduced work.
4. Copy the TOML policy and replace the application targets, keeping the evidence
   requirements and responsiveness gates unless the product has a stricter contract.
5. Use the orchestrator’s serve, record, and compare sequence, or call
   `devtools.web_performance` from another runner.
   A Chrome-based application can adapt `capture-browser.js` by replacing the ready
   condition, completion poll, and probe, keeping its fresh profile and trusted-input
   sentinel, which sends a controlled input at the settle boundary and rejects input
   outside it. Invalid evidence is refused; a hard-gate miss is kept as evidence and
   exits nonzero.
6. Keep raw run records append-only and generate summaries from them.

The framework adds no browser-automation dependency: its DevTools Protocol driver covers
an installed Chrome or Chromium, and another driver can run the same scenario if it
keeps the browser visibly foregrounded and produces the contract envelope.

## Limits

These are controlled lab measurements, not field Core Web Vitals.
Optional Chromium signals such as Long Animation Frames and `performance.memory` stay
explicit when a browser cannot provide them, and Event Timing needs real input, so the
record refuses an untouched page instead of inventing interaction performance.
Absolute timings vary with hardware and load: back-to-back controls, repeated runs,
semantic equivalence, and absolute gates carry a conclusion, and a lone percentage does
not.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
