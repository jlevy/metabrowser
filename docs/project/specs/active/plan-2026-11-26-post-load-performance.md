# Plan: Post-Load Navigation and Fetch Performance

**Date:** 2026-11-26

**Status:** Active

## Overview

Start with an already loaded Metabrowser repository.
Files, commits, pull requests, and their detail tabs should respond on the next
available frame when prepared.
When data is genuinely missing, retain useful content until the exact destination or an
actionable error can replace it.
Measure the initial paint of useful content and its stability through the rest of the
transition.

Warm the product up deliberately on a server or native app start.
Measure that phase on its own, through a declared browsing-ready boundary.
The post-warm-up phase then measures real first clicks without rehearsing their
destinations. Report what startup preparation finished and what work crosses the
boundary.

## Goals

- Measure process launch, server and repository readiness, first useful content, and
  preparation separately from later navigation.
  Where the native app can start a server or prepare its WebView sooner, measure the
  gain from app launch and the gain after repository load.
- Rank first visits, prepared first visits, and revisits on the public Metabrowser
  repository by time from trusted input to useful content.
  Include clicks with no hover dwell, hover or focus followed by a click, rapid
  navigation, and history.
- Detect blank or loading frames, unrelated-content flashes, visible movement, and
  needless replacement of unchanged content.
  Measure the exact destination separately from the previous content that kept the
  screen useful.
- Trace slow paths across browser requests and rendering, server queue and cache work,
  and external Git and GitHub CLI calls.
  Test which preparation helps users and which work consumes capacity without helping
  the next action.
- Verify GitHub behavior with bounded live reads and deterministic refusal tests.
  Record observed status, validators, resource buckets, and query costs separately from
  GitHub’s documented policy and Metabrowser’s own governor.

## Background

The [performance campaign](plan-2026-11-14-performance-campaigns.md) already measures
stateful transitions on a pinned Metabrowser clone.
Its standard run warms the server by walking the same journeys before recording.
This gives a repeatable warm-server control, but leaves a first visit after ordinary
repository load, and during competing preparation, as separate regimes to measure.
The
[PR page probe](../../../../explorations/performance-loop/README.md#pull-request-view-pairs)
starts on a new document and traces subprocess calls.
That cost is distinct from opening a PR or its Changes tab in the current document.

The
[GitHub architecture](../../architecture/arch-github-pull-requests.md#background-prefetch)
describes several independent kinds of preparation.
The pull catalog, detailed records, file lists, Git objects, route payloads, and mounted
views can each be in a different state for the same click.

## Design

Use golden-backed API cases through an actual loopback server for the fast iteration
loop. Preserve the golden response semantics with explicit field checks and compare
matched content hashes across builds.
Record server stages, response transfer, and cache behavior.
Run the browser recorder separately for rendering, first useful paint, visual
continuity, and input response.

Keep the historical transition scenario and its comparisons reproducible.
Give new journeys or metrics a revision when their meaning changes.
Separate a wiring smoke test from a judged experiment and preserve refusals.

| Layer | Evidence |
| --- | --- |
| Browser | Exact destination at the first useful frame and at convergence, first-frame and tail latency, prior/blank/placeholder frames, visible-region movement and replacement, Long Tasks, and retained memory |
| Browser-to-server | Request class and count, transferred bytes, overlap and cancellations, and which response bodies arrived before the useful frame |
| Server | Route elapsed time and reported server stages, cache state at input, coalesced work, and ordering of demand versus speculation |
| Provider | Process wall time, in-flight calls, HTTP status and allowlisted response headers, conditional hits, GraphQL cost, and local Git versus network Git work |

Sample Files, Commits and commit comparisons, Pulls and PR Conversation, Changes and
Checks. Include ordinary and large subjects and a stack or guided view when its fixture
is reliable. Freeze the corpus refs, subject identities, build, harness revision, and
browser settings. Keep live provider tests separate from pinned or replayed timings.
Distinguish the browser’s first visit, a warm server, a persistent cache, and live
GitHub. Run cold startup and large-corpus checks as guards for work moved before input.

## Implementation Plan

### Phase 1 — Revalidate the Instruments and Establish the Baseline

- [ ] Audit the web framework, development guide, runbook, campaign plans, and GitHub
  architecture against current commands, code, and evidence.
  Repair commands and predicates that have drifted.
- [ ] Run the retained harness on the pinned public Metabrowser corpus.
  Add current first-click and external fetch coverage where it is missing.
  Check sample identity, readiness, convergence, and cache state before admitting
  observations.
- [ ] Record series protocols before timed comparisons.
  Rank slow paths by regime, preserving sample counts and tails.
  Attribute the slowest paths through fetch and paint and register the next hypotheses.

### Phase 2 — Improve the Slowest Post-Load Paths

- [ ] Test startup preparation of the Commits list and newest comparison and likely
  Pulls and PR destinations.
  Measure readiness, useful prefetch coverage, and background contention as separate
  outcomes. Treat the native app’s process and WebView warm-up as part of the startup
  measurement.
- [ ] Run interleaved control and candidate measurements on the highest-cost paths.
  Test fetch ordering, reuse, and bounded preparation before changing concurrency or
  expanding the amount of work.
  Confirm the input-to-paint effect in the browser.
- [ ] Compare conditional versus unconditional reads, useful batch sizes, and modest
  concurrency within a fixed live read budget.
  Stop on rate-limit signals and exercise reset and retry behavior with controlled
  responses. Use matched work when comparing timings and report exact resource buckets
  and costs.
- [ ] Rerun the full navigation matrix on the integrated candidate.
  Verify that warm readiness and visual continuity improve without moving cost into
  startup, raising memory without bound, starving reads on screen, or increasing
  rate-limit spending without a corresponding first-visit benefit.

Record each attempt in the existing experiment ledger, with annotations for the change,
findings, and limits.
Keep diagnostic observations separate from paired results so the chart export can show
both without assigning a verdict to an unjudged run.

### Next Experiments

| Hypothesis | Intervention | Deciding result |
| --- | --- | --- |
| H125 | Prepare the default first history page once on server startup through the same history registry as Commits. | A concurrent read shares the walk. A prepared first read improves without delaying inventory readiness or the Files landing. |
| H126 | Let the selected Conversation fetch its validated metadata while the checkout store is still acquiring Git objects. | On a held acquisition, the selected header and description arrive before the store is released, with the correct viewer, one core query, and normal Changes afterwards. |
| H127 | Reuse the exact first Changes payload at the slowest observed stage. | Split acquisition, comparison, and browser hydration first. Advance the one stage that dominates time to the first visible hunk. |
| H128 | Give the selected pull priority over optional GitHub reads. | With equal responses and request budgets, measure whether withholding optional reads still helps after H126. Record refusal and retry behavior. |
| H129 | Make a short HTTP invocation run only the chosen golden-backed cases. | The recorded read set shrinks and preserves checked responses, validators, and startup clocks. |
| H131 | Prepare the shared diff renderer during browser idle after Git discovery. | Reduce asset requests after the first Commits click. Track the Files landing, useful Commits paint and layout shift separately. |
| H132 | Fetch the selected Changes commits before the wildcard checkout-origin acquisition. | Compare identical diff and final refs. Measure time to exact comparison, time to all refs, and retained pack bytes separately. |
| H133 | Let the wildcard fetch negotiate with the exact commits already obtained. | Keep the checked diff and all origin refs and recover the extra bytes of the extra fetch. |
| H134 | Vary simultaneous gh processes within one selected Conversation. | Compare the same REST responses and quota charges. Retain refusals and per-process fan-out separately from the coordinator’s job slots. |
| H135 | Treat a Pulls list with a usable row and prompt as ready while its optional changed-lines badge is pending. | Record that the list can be used. Keep the late badge in frame telemetry, and keep ordinary loading as a readiness blocker. |

Run one hypothesis per round and record results on its owning branch.
Measure a small, exact read first.
Request browser and native acceptance after the same change improves the relevant API or
rendering metric and its guards.
A busy host can still prove ordering and response equivalence.
Record its timings as diagnostics.

## Testing Strategy

Use the existing browserless and golden tests for navigation, prefetch ownership,
cancellation and GitHub refusal behavior.
Use Chrome to measure visible frame outcomes and confirm selected platform-sensitive
paths in WKWebView. Apply the existing
[acceptance rules](../../../../explorations/performance-loop/README.md#the-accept-rule)
and retain evidence for rejected changes.
Test for zero blank or placeholder frames and zero visible movement of unchanged regions
on prepared and revisited paths.
For cold paths, report both time until the target is useful and what is visibly present
before then. Verify exact final content in every regime.

## Rollout Plan

Land documentation and measurement coverage first.
Land measured product changes in behavior-focused increments with their paired evidence
and regression checks.

## References

- [Diagnostic baseline and next experiments](../../research/research-2026-11-26-post-load-performance.md)

- [Performance runbook](../../../../explorations/performance-loop/README.md)

- [Web performance framework](../../../web-performance-framework.md)

- [Instant transitions and stable layout](plan-2026-11-11-ui-apparent-performance.md)

- [GitHub REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)

- [GitHub GraphQL rate limits](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
