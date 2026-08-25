# Web Performance Framework

**Status:** Approved

## Purpose

A performance change is useful only when the application stays correct and responsive
while the named metric improves.
This framework turns that rule into a reusable browser record, an application adapter, a
budget policy, and a comparison loop.
It is designed for web applications that load progressively, maintain live state, or
continue doing work after the first paint.

Metabrowser is the reference integration.
The browser-standard parts do not know its routes or DOM; the adapter adds the moments
that make this application usable, such as its first tree row and final inventory state.

## The Four Layers

| Layer | Metabrowser implementation | Reusable responsibility |
| --- | --- | --- |
| Navigation-time recorder | `src/metabrowser/static/perf.js` | Attach before application work; retain bounded detail and exact aggregates for fetches, named spans, paint, layout stability, Long Tasks, Long Animation Frames, and Event Timing |
| Application adapter | `explorations/performance-loop/probe.js` | Add app milestones, visual states, completion, DOM size, and route attribution to the standard profile |
| Policy | `explorations/performance-loop/performance-budgets.toml` | Declare evidence requirements, hard gates, and improvement targets without embedding them in the collector |
| Orchestrator | `explorations/performance-loop/run.py`, `capture-browser.js`, and `devtools/web_performance.py` | Preserve build and corpus provenance, drive trusted Chrome input without another package, reject invalid records, compare repeated conditions, and make budget failure a nonzero result |

Metabrowser exposes the recorder as `window.metabrowser.perf`, alongside the other
supported browser and console tools.
The recorder logic remains independent of Metabrowser routes and DOM; another
application publishes the same API under its own stable namespace.
Application code contributes stable labels through `measure()` and `measureAsync()`.
Labels describe operations, never paths or other unbounded values, so whole-window
attribution stays bounded.

## Console Diagnostics

The recorder is active from before application work starts, so opening the console after
a problem does not lose the beginning of the session.
Use these commands without loading another script:

- `metabrowser.perf.report()` prints the profile and slow-operation tables;
- `metabrowser.perf.responsiveness()` returns the current main-thread and interaction
  summary;
- `metabrowser.perf.copy()` copies the complete JSON profile for a bug report;
- `metabrowser.perf.download()` saves that profile;
- `metabrowser.perf.reset()` starts a new visible measurement window.

Keep the tab visible after a reset and interact with the application before treating the
result as responsiveness evidence.
The profile says when visibility or observer coverage makes the measurement invalid.

## Measurement Contract

Every browser run is one flat JSON envelope.
The generic fields form `web-performance-profile/v1`; an adapter may add fields but may
not redefine them.

### Evidence before metrics

The loop refuses a record unless it establishes all of these facts:

- The navigation-time profiler produced the expected schema.
- The tab stayed visible for the complete window.
- Required `PerformanceObserver` signals were supported.
- Trusted pointer or keyboard input spans the progressive loading window, and Event
  Timing was available.
  The policy sets both a minimum input count and a minimum percentage from first to last
  input over the measured window.
  A fast input may produce no Event Timing entry because the browser reports only
  entries above its duration threshold; the separate count and span distinguish that
  good zero from an untouched or single-early-click page.
- The application-specific completion marker says the scenario settled.
- Application-specific readiness and correctness checks say deferred features reached
  their final state. A scenario is not settled merely because its network and render work
  stopped; a missed initialization event can make an incomplete application look
  unusually fast.
- Rendered main-panel errors and uncaught page exceptions are counted from navigation
  through export and required to be zero.
  An error message is content, but it is not a successful paint milestone.
- Application fetches are idle, so backend completion cannot end the profile while the
  browser is still consuming its result.
- The viewport clears the application’s declared floor.
- Span-label retention did not overflow.
- The Resource Timing buffer did not fill; truncated network totals are invalid, not
  low.
- The run carries corpus, build, dirty-tree, harness-version, and timestamp provenance.

A late observer is diagnostic only.
Its buffered Long Task, paint, and layout entries cannot make a run valid or overwrite
the navigation-time totals.
Missing or unsupported signals remain null or are named in `unsupported`; absence never
becomes a good zero.

### Metric coverage

| Dimension | Standard fields | What they prevent |
| --- | --- | --- |
| Loading | `ttfb_ms`, `response_download_ms`, `dom_interactive_ms`, `dcl_ms`, `load_ms`, `fcp_ms`, `lcp_ms`, plus startup script count, transfer, tail, maximum duration, and bounded path-only attribution split into response wait, server work, and download | Treating a fast shell, server response, or load event as a usable application, hiding an eager feature tier inside noisy paint timing, or guessing whether a slow asset waited on the application, server, or connection pool |
| Responsiveness | Long Task count, total, maximum, first-five-second maximum, tasks over budget, Total Blocking Time, blocked share, and application-delivery callback maximum/share | Hiding one multi-second freeze inside a total, or an event storm inside individually short callbacks |
| Frame attribution | Long Animation Frame count, maximum, blocking time, forced style/layout maximum, worst scripts and nearby resources | Knowing that the page froze without knowing which callback or rendering cost owned it |
| Interaction | Trusted-input count, first and last offset, span, loading-window coverage, plus grouped Event Timing interaction count, retained count, percentile scope, p50, p95, and exact maximum | Calling an untouched or single-early-click page responsive, counting one gesture’s several DOM events as several interactions, confusing no slow entry with no input, or reporting a bounded percentile as whole-session evidence |
| Visual stability | Navigation-time LCP and CLS’s maximum session window, plus adapter-defined movement and repaint counts | Improving first paint by assembling or moving the visible page afterwards, or reporting an all-session shift sum under the CLS name |
| Rendering and memory | Named-span counts, totals, maxima, first completion, `dom_nodes`, optional natural heap, and controlled post-profile-GC retained heap | Moving work into an unmeasured callback, growing the DOM with the corpus, mistaking garbage-collection timing for retained-state growth, including measurement-only collection in UI timing, or losing early attribution to a ring buffer |
| Network | Request count, in-flight count at capture, exact rejection/abort/4xx/5xx totals, transfer by resource class, largest and slowest resources, endpoint timings, and `Server-Timing` | Ending a profile before client work settles, losing failures from a bounded detail ring, or conflating server work with queueing, payload, and client processing |
| Backend and correctness | Scan completion, rendered main-panel error count, uncaught page-exception count, adapter-defined feature readiness and final-state checks, route samples, peak RSS, corpus fingerprint, and semantic API comparison | Buying browser speed with a missing feature, incomplete data, a renderer failure, a different answer, or cost moved behind the browser boundary |

The detail rings are intentionally bounded.
Whole-window counts, totals, maxima, milestones, and per-label aggregates are maintained
separately, so bounded retention does not erase the beginning of a bad load.
The record states how many samples were seen and retained, whether labels overflowed,
and whether the Resource Timing buffer filled.

### Standards and lab semantics

The fields follow the browser APIs rather than borrowing their names loosely.
[Event Timing](https://w3c.github.io/event-timing/) assigns the same non-zero
`interactionId` to the events in one click, tap, or key gesture.
The recorder groups on that identifier and keeps the slowest event duration for the
gesture, the unit on which [Interaction to Next Paint](https://web.dev/articles/inp) is
built. The hard gate uses the exact worst interaction in the lab run instead of INP’s
high-volume outlier rule: a reproducible six-second freeze must fail even if a long
scripted journey could statistically discard it.

[Long Tasks](https://w3c.github.io/longtasks/) provide the portable blocking totals.
[Long Animation Frames](https://w3c.github.io/long-animation-frames/) add Chromium’s
script and rendering attribution when supported.
The latter stays optional and null when absent; it never turns an unsupported observer
into a successful zero.

[Largest Contentful Paint](https://w3c.github.io/largest-contentful-paint/) and
[Layout Instability](https://wicg.github.io/layout-instability/) are also observed from
navigation. CLS is the largest shift session window, not the sum over a long-lived page.

## Budgets and Targets

The TOML policy distinguishes two kinds of limits.

**Hard gates** are properties the application currently satisfies and must never trade
away. Metabrowser’s candidate must have no task or Long Animation Frame attributed
blocking over 200 ms, no interaction over 200 ms, and no more than 5% whole-window
blocked share. An admissible progressive-load profile also needs at least five trusted
inputs spanning 80% of its measured window.
This is an evidence requirement, not a speed budget: a run that never tested the late
update stream cannot pass or fail responsiveness honestly.
Raw Long Animation Frame duration remains a target: Chromium can include a document’s
initial navigation gap even when it attributes zero blocking, rendering, scripts, and
resources to that frame, so duration alone is not evidence that the UI thread was busy.
Inventory and catalog delivery have a tighter attribution gate: no callback may cross 50
ms, and all such callbacks together may consume at most 5% of the measurement window.
Metabrowser also gates the startup JavaScript tier at 25 non-vendor requests and 175 KB;
the limits retain measured headroom above its 22-request, 154 KB directory shell while
preventing plugins or post-usable-state shell tools from returning to the critical path.
The deferred tools and their authoritative file catalog carry separate readiness gates,
so transfer cannot improve by losing controls or stopping at partial data.
Rejected non-abort fetches and HTTP 5xx responses must also remain zero; aborts and 4xx
responses stay visible as targets until a scenario can declare them intentional.
The comparison checks every candidate run, not its median: one six-second freeze is a
failure even if two clean runs would hide it statistically.

**Roadmap targets** are visible debts, such as one tree paint or zero reserved-region
movement. They are reported on every comparison but do not block unrelated work until
reached.
Once a target is achieved and defended, change its policy to `gate`; do not move
the number into prose where nothing enforces it.

All conditions need at least three admissible browser runs before `compare` succeeds.
The primary metric still needs a mechanism and non-overlapping ranges; the budget gate
is an additional constraint, not a substitute for the experiment’s accept rule.

## The Performance Loops

No single page load covers every dimension.
Use the same record and policy in focused scenarios, keeping one control variable per
round.

| Loop | Scenario | Primary measures | Invariants carried beside them |
| --- | --- | --- | --- |
| Cold load | Fresh process and origin; load through application settle | TTFB, FCP, LCP, first usable state, tail | Responsiveness, CLS, repaint count, transfer, correctness |
| Warm reopen | Reuse the process, origin, persisted state, and browser cache; reopen the same subject | Time to usable and revalidated state, cache hits, transfer avoided | Stale-state labeling, background revalidation, responsiveness, final correctness |
| Progressive load | Large or streaming data source; interact while updates arrive | Long Task and frame maxima, Event Timing, blocked share | Completion, final state, dropped/resync signals |
| Churn and recovery | Burst updates, disconnect, reconnect, and force resynchronization | Convergence time, dropped events, resync count, update coalescing | Interaction latency during churn, final semantic equivalence, bounded caches |
| Steady interaction | Settled application; repeat one scripted user journey | p50, p95, maximum interaction latency; named handler spans | Correct outcome, DOM and heap before/after |
| Stateful navigation | Settled application; move between already rendered subjects with trusted input | Intent-to-ready and selection-to-painted-ready time; blank or placeholder frames; server and client phase spans | Exact selected subject, continuous useful content, one mounted owner, bounded preparation, disposal, and heap |
| Visual stability | Fixed viewport; capture shipped, intermediate, and final states | CLS, direct region movement, visual-state and repaint counts | First usable time and responsiveness do not regress |
| Endurance | Long-lived session with repeated navigation and updates | Heap slope, DOM ceiling, retained sample counts, listener and cache sizes | Interaction latency stays flat and attribution does not overflow |
| Backend delivery | Same corpus, with and without an attached client | Scan time, route wall/server time, RSS, payload | Browser hard gates and semantic response equivalence |
| Previous-release regression | Previous published artifact and candidate, installed and alternated on one unchanged corpus | Full metric vector from the affected loops, with ranges | Semantic equivalence, every candidate hard gate, immutable build and corpus provenance |

For a new metric, first name the user-visible failure, then choose the loop that can
make the field come out bad.
A metric that can only report success is not a guard.

The previous-release row is a comparison protocol across the other loops, not a single
score. A progressively loaded application runs at least the cold-load, progressive-load,
and backend-delivery scenarios, with three or more runs per condition.
It keeps full machine reports locally, appends normalized profiles to its evidence
ledger, and commits a result document containing immutable build identities, ranges,
limits, and the decision.
An overlapping range means no detected difference; it cannot support either a win or a
regression. A candidate fails when any run crosses a hard gate or when a repeatable
wrong-way metric lacks an accepted explanation.

Stateful navigation must define useful readiness rather than accept the first paint
after input. A prompt spinner can shorten Event Timing while the requested content
arrives later. Keep the prior useful surface observable through the transition, require
the exact requested subject at a painted boundary, and record blank or placeholder
frames beside Event Timing.
Freeze the product build and browsed corpus independently when product commits would
otherwise change the navigation subjects.
Use `Server-Timing` for backend work and finite application labels for transfer,
decoding, mounting, and handoff so a cache or prefetch decision addresses the measured
layer.

An older release may predate the recorder.
A measurement-only adapter may supply the current standard observers, provided the
product code being measured stays exact and the result documents the substitution.
The adapter must preserve the release’s namespace and initialization order: creating a
current product global before an older SDK loads changes the product under observation.
Run an installed external build from a neutral working directory rather than the
candidate checkout, and verify both rendered error state and page exceptions before
accepting its timing fields.
That adapter is test instrumentation, not a reason to ship a production compatibility
layer.

## Integrating Another Application

1. Initialize one application console namespace, then load the recorder before
   application work and publish it on a stable property such as `app.perf`. Size its
   Resource Timing capacity above the largest measured scenario and keep the overflow
   check; do not assume the browser default or an arbitrary large buffer is complete.
2. Wrap stable operations with `measure(label, fn, metadata)` or
   `measureAsync(label, fn, metadata)`. Keep labels finite; put bounded diagnostic
   values in metadata.
3. Write a small adapter that reads the standard snapshot and adds the application’s
   first usable state, completion marker, visible-region changes, correctness facts, and
   the resource boundary between shell startup and selected-feature loading.
   Gate feature readiness and final data authority separately from quiescence so a
   missed callback cannot pass as reduced work.
4. Copy the TOML policy and replace the application targets.
   Keep the core evidence requirements and responsiveness gates unless the product has a
   stricter contract.
5. Use the orchestrator’s serve, record, and compare sequence, or call
   `devtools.web_performance` from another runner.
   A Chrome-based application can adapt `capture-browser.js` by replacing the ready
   condition, completion poll, and probe while retaining its fresh-profile and
   continuous trusted-input sentinel.
   Send a final controlled input at the settle boundary and freeze the standard profile
   before adapter diagnostics, so neither fast completion nor measurement work creates
   an untested tail. The driver rejects input outside that controlled pulse, so
   accidental human interaction invalidates rather than contaminates a run.
   Invalid evidence is refused; a hard-gate miss is retained as evidence and exits
   nonzero immediately.
6. Keep raw run records append-only and generate summaries from them.

The framework intentionally adds no browser-automation dependency.
Its small DevTools Protocol driver covers an installed Chrome or Chromium; a signed-in
or embedded browser can still drive the same scenario as long as it remains visibly
foregrounded and produces the contract envelope.
Changing the driver does not change the metrics, adapter, policy, or stored records.

## Limits

These are controlled lab measurements, not field Core Web Vitals.
Optional Chromium signals such as Long Animation Frames and `performance.memory` remain
explicit when a browser cannot provide them.
Event Timing needs real input, so the record refuses an untouched page instead of
inventing interaction performance.

Absolute timings vary with hardware and concurrent load.
Back-to-back controls, repeated runs, semantic equivalence, and absolute responsiveness
gates carry the conclusion; a lone percentage does not.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
