---
title: Git Revision Navigation Performance
description: Measured plan for fast, stable transitions between commit comparisons in the Git history view
author: Joshua Levy (github.com/jlevy) with LLM assistance
---
# Feature: Git Revision Navigation Performance

**Date:** 2026-08-25 (last updated 2026-08-25)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Approved

## Overview

Selecting adjacent commits in the Git history should feel like moving through one
continuous surface.
The current path removes the visible commit, shows a blocking loading
state, fetches commit metadata, and only then loads and renders the comparison.
That ordering creates an avoidable blank transition and serializes work that can run in
parallel.

This change keeps the previous revision visible until its replacement is ready, prepares
the selected comparison concurrently with commit metadata and plugin assets, and uses
bounded intent prefetching.
It also adds a repeatable real-browser scenario to the existing performance loop so
server, transfer, client rendering, and paint costs remain separable.

## Goals

- Remove blank frames when moving between already rendered Git revisions
- Start independent commit-detail, diff-asset, and comparison work concurrently
- Reuse a comparison prepared by pointer or keyboard intent without issuing a duplicate
  request
- Keep speculative work bounded to one comparison and cancel or replace stale intent
- Measure cold and prepared revision transitions in a visible real browser, including
  server time, client data time, mount time, paint readiness, long work, payload size,
  and blank-frame duration
- Preserve route ownership, rapid-selection correctness, plugin disposal, keyboard and
  pointer behavior, and reduced-motion preferences

## Non-Goals

- Prefetching comparison data for every visible history row
- Changing Git history pagination or virtualization; the
  [unbounded Git history plan](plan-2026-08-25-unbounded-virtualized-git-history.md)
  owns those concerns
- Adding a server cache before measurements show that server computation dominates
- Hiding latency with decorative motion or introducing a new animation library
- Changing comparison semantics, diff highlighting, or the public plugin SDK

## Background

The Git panel currently replaces the preview with a spinner before awaiting
`/api/git/commit/<revision>`. Only after that response does it load the diff plugin,
request `/api/plugin/diff/comparison`, and mount the comparison.
A previous diff mount is disposed before any replacement data is ready.
This produces both the empty visual handoff and a serial request waterfall.

Direct measurements against this repository on 2026-08-25 show that settled server work
is material but not sufficient to explain a long blank screen:

| Sample | Commit Detail | Comparison | Comparison Bytes |
| --- | ---: | ---: | ---: |
| Current head | 73.9 ms | 118.5 ms | 238,641 |
| Small plan commit | 24.5 ms | 88.7 ms | 56,909 |

Across the newest 12 revisions, comparison requests took 71–169 ms and returned about
1.45 MB in total, with individual responses from 2,457 to 438,612 bytes.
These figures are machine-specific diagnostic evidence, not product budgets.
They establish two design facts: independent requests should overlap, and prefetching
every visible comparison would perform substantial low-confidence work.

The existing file-selection path already uses the desired perceptual rule: keep the
prior file visible and delay a loading indicator for 120 ms.
The Git path should follow the same rule while retaining its own lifecycle and
comparison-specific preparation.

## Design

### Revision Preparation

`git-panel.js` will represent preparation as one revision-scoped operation containing:

- the bounded commit-detail request
- eager acquisition of the already registered or on-demand diff assets
- one comparison-data promise from the diff plugin’s existing data hook

Selection starts all independent work together.
Pointer entry and keyboard focus start the same operation immediately; the native hover
text retains its debounce, but data preparation does not wait for the tooltip timer.
An in-flight detail request is shared with the existing bounded detail cache.

Comparison preparation uses a single replaceable slot rather than an entry-count cache.
Only the latest intent may retain one speculative comparison.
A new intent aborts stale speculative work when possible.
Selecting the prepared revision consumes that slot; selecting another revision replaces
it. This bounds speculative comparison data independently of the number of visible
commits and avoids inventing an arbitrary multi-megabyte cache budget.

The diff view accepts a prepared document through the existing internal render context’s
`raw` field. Direct diff views continue fetching their own document.
The plugin validates and renders both paths identically, so preparation changes
transport ordering rather than the comparison model or renderer.

### Atomic Visual Handoff

Selecting a revision immediately updates row selection and the commit route, but the
existing preview and mounted diff remain alive while the replacement prepares.
After 120 ms, the preview receives a lightweight pending state and `aria-busy="true"`;
it is not replaced by a spinner.
When commit metadata and the validated comparison surface are ready, one preview
replacement installs the new commit and transfers lifecycle ownership to its diff
handle. Only then is the prior handle disposed.

Rapid selections use the existing preview claim and selected revision checks at every
await boundary. A stale operation may populate the bounded detail cache, but it cannot
replace the preview or own the mounted diff.
A failed selected operation replaces the retained preview with an explicit failure state
and clears pending accessibility state.

A short opacity transition may soften the completed swap using existing motion tokens.
It must not delay readiness, animate large geometry, or run when
`prefers-reduced-motion` is enabled.

### Performance Attribution

Production instrumentation adds revision-scoped measures for:

- commit-detail data readiness, including JSON decoding
- diff-asset readiness
- comparison-data readiness, including JSON decoding
- commit markup and diff mounting
- selection to the first painted ready frame

The existing fetch recorder supplies request duration to response headers and
`Server-Timing` for server attribution.
The new labels cover the remainder of transfer, JSON decoding, DOM work, and renderer
work.

The performance loop gains a Git revision scenario built on its dependency-free Chrome
DevTools Protocol driver.
It opens the Git panel, warms one commit, then uses trusted clicks to traverse cold
revisions and revisit a prepared revision.
Each transition records:

- selected and ready revision IDs
- total time to a double-animation-frame ready boundary
- commit-detail and comparison request totals, server times, and response sizes
- measured client phases, Long Tasks, Long Animation Frames, and page exceptions
- whether prior commit content remained continuously present before the swap
- retained heap and mounted comparison count after the sequence

The scenario runs at least three times per condition against an unchanged corpus and
visible Chrome. Baseline and candidate runs alternate order.
A claimed improvement requires nonoverlapping ranges for the target metric, no blank
interval in candidate transitions, no new exception, and no regression in maximum long
work or retained mounted resources.

### API and Compatibility

No server route or external dependency changes.
The server, shell, and built-in diff plugin ship together, so passing prepared
comparison data through the existing internal render context is an atomic internal
change. No compatibility layer is needed.

## Implementation Plan

### Phase 1: Measure and Improve Revision Navigation

- [ ] Add behavior tests for shared in-flight detail work, single-slot comparison
  preparation, concurrent selection work, retained-preview handoff, stale selection,
  failure, disposal, and reduced motion
- [x] Add the Git revision scenario and its output validation to the performance loop
- [x] Capture at least three baseline scenario runs on the unchanged build
- [ ] Implement revision preparation, prepared diff rendering, performance labels, and
  the atomic visual handoff
- [ ] Capture at least three candidate scenario runs and record the result as a
  performance experiment
- [ ] Update engineering and performance documentation, run focused tests, exercise the
  result in a real browser, and run `make format` and `make verify`

## Testing Strategy

The fake-DOM Git panel suite will pin request sharing, ordering, stale-operation
behavior, preview continuity, accessibility state, and exact disposal.
Diff plugin tests will verify that prepared and fetched documents follow the same
validation and mount path.
Static design tests will pin tokenized transitions and reduced-motion behavior.

The CDP scenario will provide end-to-end evidence on the repository itself.
Manual real-browser validation will cover fast repeated pointer and keyboard navigation,
error recovery, direct commit routes, large and small comparisons, fold controls, split
and unified layouts, theme contrast, and absence of flicker.

## Rollout Plan

The shell and built-in plugin ship as one artifact.
Land the complete client, plugin, scenario, tests, experiment, and documentation change
together. No feature flag or data migration is required.

## Open Questions

None. Further server caching or adjacent-row background prefetching requires a separate
measurement showing that the bounded selected-and-intent path is insufficient.

## References

- [Git graph view plan](plan-2026-08-06-git-graph-view.md)
- [Unbounded Git history plan](plan-2026-08-25-unbounded-virtualized-git-history.md)
- [Load-time performance plan](plan-2026-08-21-load-time-performance.md)
- [Rendering large content](../../../large-content-rendering.md)
- [Web Performance Framework](../../../web-performance-framework.md)
- [Performance loop](../../../../explorations/performance-loop/README.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
