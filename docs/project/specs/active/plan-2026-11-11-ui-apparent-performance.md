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

- A switch between main tabs, and a return to anything already shown, paints in one
  frame with no data request.
- No region of the shell or a page header moves during or after a transition unless the
  reader’s own input moved it.
- The work a click waits on is prepared before the click, behind admission control that
  never lets background work delay a foreground request.
- Every change is a measured round of the performance loop, recorded whether it is
  accepted or rejected, and the campaign ends with a performance summary for every item.

## Non-Goals

- Native shell code. The sticky port, web view prewarming, hidden load with reveal on
  ready, and a spare web view belong to `apps/macos`, which stays unmerged until the
  owner says otherwise.
  This plan does the server and browser half those depend on and records the shell half
  as deferred beads.
- A persisted index or first-rows snapshot across restarts; that is the native
  topology’s later phase.
- Changing what any view shows, beyond fixing its layout.

## Background

The research measured 130 transitions in Chrome and the delivery path in a real
`WKWebView`. Its main findings: main tabs destroy and rebuild the preview; nothing is
reused on a revisit; rendered Markdown is a POST of the whole source on every view; most
layout shift is chrome that toggles; the cold landing is about 23 dependent request
levels deep; every load revalidates 33–84 assets; and WebKit lacks
`requestIdleCallback`, Long Tasks, and the Layout Instability API.

## Design

### Approach

Three rules carry the design:

1. **Retain, don’t rebuild.** A surface the reader may return to keeps its DOM, and the
   few most likely to be returned to keep their layout.
2. **Fix every region’s box at first paint.** Chrome that can appear reserves its slot;
   anything that arrives later fills a box whose size was already known.
3. **Prepare behind a lane.** Prediction warms the whole chain for the next subject, at
   low priority, at most two background requests at a time.

### Components

- **Shell:** `static/app.js` (file render, view tabs, claims), `static/main-tabs.js`,
  `static/navigation.js`, `static/asset-loader.js`, `static/plugin-sdk.js`,
  `static/styles.css`, `static/perf.js`.
- **Built-in plugins:** `builtin_plugins/markdown/` (render chain, worker),
  `builtin_plugins/github/` (PR page, Pulls panel), `static/git-panel.js`.
- **Server:** `server.py` (shell, headers, compression, `Server-Timing`),
  `plugin_loader/static_assets.py`, `kpress_adapter.py`, `git/` routes.
- **Measurement:** `explorations/performance-loop/` (a transition scenario, its records,
  and the budgets).

### API Changes

- A view may implement optional `suspend()` and `resume()` hooks so the shell can retain
  it detached or hidden; a view without them keeps today’s rebuild.
  This changes the plugin SDK, so `PLUGIN_SDK_VERSION` and every built-in manifest move
  together, with a `CHANGELOG.md` entry.
- Background fetches carry `priority: "low"`; the server admits them behind foreground
  work.
- Rendered Markdown becomes addressable by path, content identity, and options through a
  GET, so it can be prefetched and cached.

## Implementation Plan

Each item is one round of the performance loop: its hypothesis is registered in
[the load-time plan](plan-2026-08-21-load-time-performance.md#apparent-speed-and-layout-stability),
its experiment record lands with its code, and its bead closes on the recorded verdict.
Phases are PR boundaries; items within a phase may share a PR when they touch the same
files.

### Phase 1: Measurement and Quick Wins

- [ ] A transition scenario that records painted-ready, blank frames, region movement,
  layout-shift entries, and requests per transition; a baseline round
- [ ] `Server-Timing` spans through the end of the body, and a WebKit-aware recorder
  (idle and frame-gap shims)
- [ ] Reserve every toggling chrome slot, and fix each PR page header section’s box at
  first paint (the per-section layout spec in the research)
- [ ] Caching headers: immutable stamped assets, content-keyed plugin and KPress
  prefixes, working `/raw` conditionals
- [ ] Git: comparison cache by commit ID in the browser, route memo by refs fingerprint
  on the server
- [ ] Parallel `shell-tools` and KPress asset loading
- [ ] Render payload cache and a long-lived Markdown worker
- [ ] Prose font preload, no animation on programmatic tree reveals, held-key
  coalescing, fixed palette group order
- [ ] PR page: join the click to the peek, same-frame list collapse and expand, hold
  Changes first paint for diffs in flight
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

- [ ] Sticky port, one host spelling, persistent data store
- [ ] Prewarm at launch, hidden load, reveal on ready, one spare web view
- [ ] Persisted first-rows snapshot

## Testing Strategy

- Every behavior change follows the repository’s parity rules: data semantics through a
  route and a golden; browser-owned state machines through browserless sessions against
  the production JavaScript.
- Retention gets disposal tests: a retained view is disposed exactly once, on eviction
  or replacement, and a suspended view does no work.
- Each round’s measurement uses the transition scenario on the same corpus, control
  against candidate, interleaved, with the accept rule and tolerances of
  [the runbook](../../../../explorations/performance-loop/README.md#the-accept-rule).
- The final round re-measures every accepted item together against the baseline, in
  Chrome and, for request counts, in `WKWebView`.

## Rollout Plan

Each PR merges to `main` after review and green CI. The campaign summary lands with the
final round.

## Open Questions

- Whether the tree-first startup order still pays for itself once assets are cached
  (`app.js:8374-8378`); Phase 2 re-measures it before changing it.
- How many laid-out surfaces the memory budget allows inside one web view; the
  retained-surface rounds measure it.

## References

- [Apparent UI performance for the native app](../../research/research-2026-11-11-ui-apparent-performance.md)
- [Load-time performance plan](plan-2026-08-21-load-time-performance.md)
- [Performance-loop runbook](../../../../explorations/performance-loop/README.md)
- [Native macOS app plan](plan-2026-11-10-native-macos-app.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
