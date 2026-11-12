# Feature: Instant Transitions and Stable Layout

**Date:** 2026-11-11

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Approved

## Overview

Make every transition in the browser UI paint its destination at once, with no blank or
loading frame and no content that moves after it appears, and make the shell load as
fast as its engine allows inside the native app’s `WKWebView`. The findings,
measurements, and ranking this plan implements are in
[apparent UI performance for the native app](../../research/research-2026-11-11-ui-apparent-performance.md).

## Goals

- A switch between main tabs, and a return to anything already shown and unchanged,
  makes no data request and reaches painted ready within the research’s 50 ms budget.
  The measured costs say which retention tier meets it.
  A laid-out surface of up to a few thousand elements shows in the next frame.
  A detached one takes one or two frames plus 6 to 37 ms of style and layout: inside the
  budget for ordinary files, at its edge for long documents.
  The largest source file measured needs 106 ms detached and 29 ms laid out, so it needs
  the laid-out tier.
- No region of the shell or a page header moves during or after a transition unless the
  reader’s own input moved it.
- The work a click waits on is prepared before the click, behind admission control that
  never lets background work delay a foreground request.
- Every change is a measured round of the performance loop, recorded whether it is
  accepted or rejected, and the campaign ends with a performance summary for every item.

## Non-Goals

- Native shell code. Web view prewarming, hidden load with reveal on ready, a spare web
  view, one host spelling, and a persistent data store belong to `apps/macos`, which
  stays unmerged until the owner says otherwise.
  This plan does the server and browser half those depend on and records the shell half
  as deferred beads. The sticky port is not shell code: it is `metab` host mode
  (`mb-qzny`), core work that lands on `main` under the
  [native app plan](plan-2026-11-10-native-macos-app.md#milestone-v1-a-usable-app).
  This plan depends on it for H87’s relaunch metric rather than doing it.
- A persisted index or first-rows snapshot across restarts (`mb-54k9`); that is the
  native topology’s later phase.
- Visual restyling. Layout rules that fix a section’s box at first paint are in scope,
  because the owner asked that each section have a clear, clean layout so that nothing
  shifts. Each rule states its cost to the reader in the research’s
  [section-by-section rules](../../research/research-2026-11-11-ui-apparent-performance.md#page-headers-section-by-section),
  and `docs/design-system.md` changes in the pull request that implements a rule it
  contradicts, such as the print action that is absent when nothing is printable.

## Background

The research measured 130 transitions in Chrome and the delivery path in a real
`WKWebView`. Its main findings: main tabs destroy and rebuild the preview; nothing is
reused on a revisit; rendered Markdown is a POST of the whole source on every view; most
layout shift is chrome that toggles; the cold landing is about 23 dependent request
levels deep; every load revalidates 33–84 assets; and WebKit lacks
`requestIdleCallback`, Long Tasks, and the Layout Instability API.

This campaign follows two others that touch the same paths.
The November 4 iteration (`mb-4ifm`) registered and measured H74 to H85 for PR and Git
navigation, and several of its accepted results are guards here.
The PR freshness and prefetch work (#355) added a provider prefetch lane with its own
budgets. The registry’s
[introduction to this campaign](plan-2026-08-21-load-time-performance.md#apparent-speed-and-layout-stability)
says which new rows revisit which earlier ones.

## Design

### Approach

Three rules carry the design:

1. **Retain, don’t rebuild.** A surface the reader may return to keeps its DOM, and the
   few most likely to be returned to keep their layout.
2. **Fix every region’s box at first paint.** Chrome that can appear reserves its slot;
   anything that arrives later fills a box whose size was already known.
3. **Prepare behind a lane.** Prediction warms the whole chain for the next subject, at
   low priority, under a cap on background requests in flight.
   The cap starts at two; the research measured saturation at five connections, not the
   cap, so H93 sets it.

### Components

- **Shell:** `static/app.js` (file render, view tabs, claims), `static/main-tabs.js`,
  `static/navigation.js`, `static/asset-loader.js`, `static/plugin-sdk.js`,
  `static/styles.css`, `static/perf.js`.
- **Built-in plugins:** `builtin_plugins/markdown/` (render chain, worker),
  `builtin_plugins/github/` (PR page, Pulls panel), `static/git-panel.js`.
- **Server:** `server.py` (shell, headers, compression, `Server-Timing`),
  `plugin_loader/static_assets.py`, `kpress_adapter.py`, `git/` routes.
- **Design system:** `docs/design-system.md`, updated by each pull request whose layout
  rules change what a section shows.
- **Measurement:** `explorations/performance-loop/` (the transition scenario, its
  records, the budgets, and a committed `WKWebView` probe).

### Retained Surfaces and Staleness

A retained surface is shown again without a data request only while what it shows is
current. Each tier takes its invalidation from a source that already exists:

- **File surfaces**, detached or laid out, including the hidden view tabs of the open
  file: keyed by path, envelope ETag, and active view.
  They are flagged by the same sources that flag `fileCache` today: a change event marks
  the path in `fileNeedsRevalidate`, and a snapshot replacement flags every cached path
  (`app.js:6452-6454`). A flagged surface is revalidated with `If-None-Match` before it
  is shown, as a flagged `fileCache` entry is (`app.js:5310-5325`): a `304` re-attaches
  it and a `200` renders the new envelope.
  Active, appending files are never retained, as `fileCache` already excludes them.
- **The Commits surface:** a comparison named by a full commit ID cannot change, so a
  retained commit view is never stale.
  The history list keeps its existing refresh, now keyed by the refs fingerprint of the
  git route memo (H88).
- **The Pulls surface:** a retained pull request page does no work while suspended.
  On resume its first read asks whether the record changed, and a changed record patches
  the body in place (H106), as a revisit does today.

While a revalidation is on its way the previous surface stays on screen, as the staged
render keeps the old file today: a reader returning to a flagged surface keeps seeing
what was on screen until the check answers, never a blank or a spinner before
`--loading-state-delay`.

### Background Lanes

Two lanes govern background work, and they govern different things:

- **Admission control** (H93) governs the HTTP requests the page sends in the
  background: prefetches of envelopes, renders, and kind assets; the Pulls walk’s steps
  (`pulls?…&after=N` and `pull-cores-prepare`, `CORE_PREPARE_ROUTE` at
  `pulls-panel.js:52`); and `pulls-prefetch` requests (`PREFETCH_ROUTE`,
  `pulls-panel.js:53`). Each counts against the cap while it is in flight, because each
  holds one of the six connections and server time.
  Foreground requests never wait for the cap.
- **The provider prefetch lane**
  ([PR freshness and prefetch](plan-2026-11-11-pr-freshness-and-prefetch.md#the-prefetch-lane))
  governs work that spends GitHub budget: one job at a time per repository, caps per
  catalog publication and per hour, the rate-limit governor, and preemption and
  promotion by a reader.
  A `pulls-prefetch` request that answers `202` has started a job there; the job holds
  no HTTP connection and is not counted again.

H93 is judged on foreground latency under both, and on the background work still
finishing.

### API Changes

- A view may implement optional `suspend()` and `resume()` hooks so the shell can retain
  it detached or hidden; a view without them keeps today’s rebuild.
  The hooks are additive, so `PLUGIN_SDK_VERSION` does not change: the repository bumps
  it only when the contract actually breaks
  ([compatibility](../../../development.md#compatibility-and-legacy-code)).
  `CHANGELOG.md` notes the hooks for plugin authors.
  A bump, with every built-in manifest in the same commit, happens only if an
  implementation turns out to break the contract.
- Background fetches carry `priority: "low"`; the server admits them behind foreground
  work.
- Rendered Markdown becomes addressable by path, content identity, and options through a
  `GET`, so a landing can request it at once and the answer can be cached.
  Preparation stays where it runs today, in the Markdown plugin’s worker
  (`wiki-parser.js`, `rendered.js:160-181`): one implementation, the one the tests
  cover. The server answers the `GET` from the render it already holds for that key,
  filled by an earlier `POST` of the prepared source or, after a restart, by the
  persisted render cache (H102); on a miss the client runs today’s chain.
  The cost is that the first landing ever on a file is not helped: the `GET` serves
  reloads, relaunches, a second window, and later landings.
  Prediction does not need it: the prepare unit runs today’s chain in the background and
  fills the client’s payload cache (H90). Running the preparation on the server would
  help the first landing too, at the price of a second implementation of wiki
  preparation to keep in step with the tested JavaScript.
  H96 measures the landing first, and takes that alternative only if the cached `GET`
  cannot meet the content-request budget.

## Implementation Plan

Each item is one round of the performance loop: its hypothesis is registered in
[the load-time plan](plan-2026-08-21-load-time-performance.md#apparent-speed-and-layout-stability),
its experiment record lands with its code, and its bead closes on the recorded verdict.
A phase is a group of pull requests: a pull request holds items of one phase only, and
items share a pull request when they touch the same files.

### Phase 1: Measurement and Quick Wins

- [ ] A transition scenario (`mb-4z4u`) that records painted-ready, blank frames, region
  movement, layout-shift entries, and requests per transition, and a baseline round
  (exp-058). It sits beside the committed `file-views` and `git-revisions` scenarios,
  which keep their own gates.
  Its painted ready ends one frame after the first frame that shows the subject, as the
  research’s inventory did, while theirs waits two animation frames after ready, so
  values are not compared across the scenarios.
- [ ] A committed `WKWebView` measurement probe under `explorations/` (`mb-fevz`): an
  instrument, not app code, for the rows that must be read in WebKit
- [ ] `Server-Timing` spans through the end of the body, and a WebKit-aware recorder
  (idle and frame-gap shims)
- [ ] Reserve every toggling chrome slot, and fix each PR page header section’s box at
  first paint (the per-section layout spec in the research)
- [ ] Caching headers: immutable stamped assets, content-keyed plugin and KPress
  prefixes, working `/raw` conditionals
- [ ] Git: comparison cache by commit ID in the browser, route memo by a refs
  fingerprint read without running Git on the server
- [ ] Parallel `shell-tools` and KPress asset loading
- [ ] Render payload cache and a long-lived Markdown worker
- [ ] Prose faces loaded before the first document’s swap, no animation on programmatic
  tree reveals, held-key coalescing, fixed palette group order
- [ ] PR page: one read of the selected record per selection (an answer the selection
  just read is the page’s first read, the hover timer does not re-read the clicked row,
  and the row already shown reads nothing), a row’s file tree opened once at its full
  height, and Changes’ first paint held for diffs in flight
- [ ] PR page body final at first paint: Markdown cached by record revision, the body
  patched in place when the full record lands, commits delivered with the record

### Phase 2: Instant Transitions

- [ ] Admission control for background work
- [ ] One prepare unit per subject, with the addressable render GET and prediction
- [ ] Per-main-tab retained surfaces
- [ ] Collapse the cold landing chain
- [ ] First-view readiness that does not depend on visibility

### Phase 3: Deeper Retention and Render Cost

- [ ] Detached LRU of file surfaces with the `suspend()` and `resume()` contract
- [ ] Keep hidden view tabs laid out; chunk long source views
- [ ] One layout per Markdown mount
- [ ] Syntax highlighting in a worker
- [ ] Persistent render cache and retained encoded bodies
- [ ] An opt-in uncompressed mode for the app’s loopback client
- [ ] Bulk Pulls metadata warming when steps are cache reads
- [ ] Pre-mount non-default view tabs at idle

### Deferred to the Native Shell

- [ ] One host spelling and a persistent data store, using the sticky port of `metab`
  host mode (`mb-w4kd`, blocked by `mb-qzny`)
- [ ] Prewarm at launch, hidden load, reveal on ready, one spare web view (`mb-25nv`)

## Testing Strategy

- Every behavior change follows the repository’s parity rules: data semantics through a
  route and a golden; browser-owned state machines through browserless sessions against
  the production JavaScript.
- Each structural layout rule, such as a slot that exists on every tab or a row that
  always renders, also gets a browserless DOM-session assertion, because nothing in
  `make verify` runs the performance loop.
- Retention gets disposal tests: a retained view is disposed exactly once, on eviction
  or replacement, and a suspended view does no work.
- Retention gets staleness tests: a retained file surface whose path a change event
  flagged is never shown again without its revalidation, and a resumed pull request page
  reads its record before treating it as current.
- Each round compares an interleaved control, the build immediately before that item’s
  commits, against its candidate on the same corpus, with the accept rule and tolerances
  of [the runbook](../../../../explorations/performance-loop/README.md#the-accept-rule).
- exp-058 is the campaign’s reference, not a round’s control: it measured the product at
  `main` 09903292 on the corpus checkout frozen at 7a02fed4. The final round (exp-079)
  re-measures every accepted item together against it in Chrome, and counts requests in
  `WKWebView` once the probe (`mb-fevz`) is committed; until then the summary says
  WebKit was not measured.

## Rollout Plan

Each PR merges to `main` after review and green CI. The campaign summary lands with the
final round.

## Open Questions

- Whether the tree-first startup order still pays for itself once assets are cached
  (`app.js:8374-8378`); Phase 2 re-measures it before changing it.
- How many laid-out surfaces the memory budget allows inside one web view; the
  retained-surface rounds measure it.
- Whether the render `GET` from the server’s cache meets the cold-landing budget, or
  preparation must also run on the server; H96 decides.

## References

- [Apparent UI performance for the native app](../../research/research-2026-11-11-ui-apparent-performance.md)
- [Load-time performance plan](plan-2026-08-21-load-time-performance.md)
- [PR freshness and prefetch](plan-2026-11-11-pr-freshness-and-prefetch.md)
- [Performance-loop runbook](../../../../explorations/performance-loop/README.md)
- [Native macOS app plan](plan-2026-11-10-native-macos-app.md)
- [Design system](../../../design-system.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
