---
title: Git Revision Navigation Performance
description: Measured plan for fast, stable transitions between commit comparisons in the Git history view
author: Joshua Levy (github.com/jlevy) with LLM assistance
---
# Feature: Git Revision Navigation Performance

**Date:** 2026-08-25 (last updated 2026-08-25)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Implemented; PR handoff in progress

## Overview

Selecting adjacent commits in the Git history should feel like moving through one
continuous surface. The prior path removed the visible commit, showed a blocking loading
state, fetched commit metadata, and only then loaded and rendered the comparison.
That ordering creates an avoidable blank transition and serializes work that can run in
parallel.

This change keeps the previous revision visible until its replacement is ready, prepares
the selected comparison concurrently with commit metadata and plugin assets, and uses
bounded intent prefetching.
It also adds a repeatable real-browser scenario to the existing performance loop so
server, transfer, client rendering, and paint costs remain separable.
That scenario includes a large-comparison stress phase so request fanout, obsolete
completions, and selection/render divergence fail validation instead of remaining
console-only evidence.

## Goals

- Remove blank frames when moving between already rendered Git revisions
- Start independent commit-detail, diff-asset, and comparison work concurrently
- Reuse a comparison prepared by pointer or keyboard intent without issuing a duplicate
  request
- Give Git history rows the file tree’s one-stop Tab order and Arrow Up/Arrow Down
  focus-and-open behavior
- Put aggregate file, addition, and deletion counts with the commit identity above the
  commit description, without repeating them in the hosted diff
- Present the revision as a path-like copyable identifier that displays the short ID and
  copies the full commit ID through the shared copy affordance
- Keep speculative work bounded to one comparison and cancel or replace stale intent
- Stop deferred hydration and syntax work from a retained revision as soon as another
  revision is selected
- Measure cold and prepared revision transitions in a visible real browser, including
  server time, client data time, mount time, paint readiness, long work, payload size,
  and blank-frame duration
- Fail the standard Git scenario when deferred hydration exceeds its concurrency bound,
  an obsolete file request completes after selection, or row, route, and rendered
  revision diverge
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

The prior Git panel replaced the preview with a spinner before awaiting
`/api/git/commit/<revision>`. Only after that response did it load the diff plugin,
request `/api/plugin/diff/comparison`, and mount the comparison.
A previous diff mount was disposed before any replacement data was ready.
This produced both the empty visual handoff and a serial request waterfall.

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

`git-panel.js` represents preparation as one revision-scoped operation containing:

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
Deferred file sections begin hydration only when they enter the visible scroll area.
The mounted handle cancels queued observations, active hydration, syntax, timer, and
yielding work at that point while leaving its rendered DOM intact.
Obsolete work therefore cannot saturate the server or client while the selected
comparison prepares.
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

The profiler also retains the maximum simultaneous application fetches for the current
measurement window and per request class.
Query values are excluded from request-class keys, except that deferred file hydration
is distinct from its comparison-manifest request.
The distinction lets the Git scenario enforce the renderer’s two-request hydration bound
without treating the selected revision’s metadata and manifest requests as deferred
fanout.
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

Epic `mb-fgcg` owns this plan.
Its ten child beads separate measurement, behavior, presentation, validation, keyboard
consistency, commit-header information design, component ownership, retained-work
cancellation, and delivery.
Blockers express only real sequencing; the baseline also feeds final validation
directly.

| Phase | Bead | Depends On | Status |
| --- | --- | --- | --- |
| Instrument the interaction and capture the baseline | `mb-800q` | None | Closed |
| Add bounded preparation and the atomic handoff | `mb-32kx` | `mb-800q` | Closed |
| Polish pending and completed transitions | `mb-tjcl` | `mb-32kx` | Closed |
| Compare, validate, and document | `mb-8j0r` | `mb-800q`, `mb-tjcl` | Closed |
| Enforce navigational-row keyboard parity | `mb-xmkn` | `mb-8j0r` | Closed |
| Move the change summary into the commit metadata header | `mb-j0um` | None | Closed |
| Make the revision a shared copyable identifier | `mb-wchz` | None | Closed |
| Consolidate the Git commit summary component | `mb-lk26` | None | Closed |
| Cancel obsolete retained-diff work | `mb-k9a5` | `mb-32kx` | In progress |
| Complete the PR and CI handoff | `mb-j8ni` | `mb-xmkn`, `mb-j0um`, `mb-wchz`, `mb-lk26`, `mb-k9a5` | Blocked |

### Phase 1: Instrument and Baseline (`mb-800q`)

- **Files and functions:** Extend `capture-browser.js` through `parseArgs`, `usage`,
  `dispatchTrustedClickForSelector`, `dispatchTrustedPointerForSelector`,
  `startGitBlankFrameMonitor`, `stopGitBlankFrameMonitor`, `waitForGitRevision`,
  `measureGitTransition`, `runGitRevisionScenario`, and `capture`. Expose the scenario
  through `run.py` in `cmd_capture` and the capture parser.
  Update `tests/test_browser_performance_capture.py` and the performance-loop README.
- **Behavior and invariants:** Warm one commit, select two cold revisions, prepare one
  revision with trusted pointer intent, and record exact selected and painted-ready
  revisions, blank frames, request and `Server-Timing` attribution, client phase labels,
  long work, page exceptions, retained heap, and mounted comparison count.
  The default initial-load profile keeps its existing schema; the interaction scenario
  has the separate `git-revision-navigation/v1` envelope and cannot enter the
  initial-load ledger.
- **Acceptance:** Argument and output-shape tests pass.
  The scenario rejects missing rows or readiness, extra mounts, uncaught exceptions, and
  unknown scenario names.
  Three visible-Chrome baseline runs use the unchanged product and one frozen corpus.

### Phase 2: Prepare and Swap (`mb-32kx`)

- **Files and functions:** Update `git-panel.js` in `fetchCommitDetail`,
  `beginDiffPreparation`, `prepareRevision`, `cancelSpeculativePreparation`,
  `clearPendingState`, `afterNextPaint`, `selectCommit`, `renderCommitDetail`,
  `mountCommitDiff`, and `disposeCommitDiff`. Add the internal `renderPreviewNode` seam
  beside `renderPreviewHtml` in `app.js` and declare it in `types.d.ts`. Let the diff
  plugin `view.render` consume prepared `ctx.raw` in `builtin_plugins/diff/index.js`.
  Cover the behavior in `tests/dom/git-panel-behavior.js` and the shell contract in
  `tests/test_browser_loading_delay.py`.
- **Behavior and invariants:** Share in-flight commit detail, start detail, diff assets,
  and comparison data concurrently, and retain at most one replaceable speculative
  comparison. Selection consumes matching prepared data without a duplicate request;
  direct diff views retain their fetch path.
  The previous commit and renderer stay mounted until the detached replacement is
  complete. Exact revision and preview-claim checks guard every await boundary, and stale
  or replaced renderer handles dispose exactly once.
- **Acceptance:** Focused tests cover concurrency, duplicate suppression, single-slot
  replacement and abort, route ownership, selected-revision races, failure recovery,
  staged continuity, and disposal.
  Production measures name detail, assets, comparison, markup, mount, and
  selection-to-ready work.
  No server route, public SDK, dependency, or compatibility layer changes.

### Phase 3: Polish the Transition (`mb-tjcl`)

- **Files and functions:** Add the Git pending rules and reduced-motion override in
  `styles.css`; use `clearPendingState` and the 120 ms timer in `git-panel.js`; extend
  `tests/dom/git-panel-behavior.js` and `tests/test_design_vocabulary.py`.
- **Behavior and invariants:** Existing content remains visible and becomes
  `aria-busy="true"` only after the shared 120 ms grace.
  A progress cursor and existing opacity motion token soften a slow handoff without
  animating geometry or delaying readiness.
  `prefers-reduced-motion` removes the transition.
  A spinner appears only when no prior commit surface exists.
- **Acceptance:** Pending state clears on success, failure, stale ownership, refresh,
  and disposal. CSS uses design tokens, keyboard and pointer selection stay usable, and
  tests pin the reduced-motion and no-blank contracts.

### Phase 4: Compare, Validate, and Document (`mb-8j0r`)

- **Files and functions:** Record
  [exp-018](../../../../explorations/performance-loop/experiments/exp-018-git-revisions-swap-without-blanking.md),
  update the performance-loop README, this plan, the load-time hypothesis registry,
  `web-performance-framework.md`, and `CHANGELOG.md`. Update the architecture registry
  only if a registered view, route, model, or format changes; this implementation adds
  none.
- **Behavior and invariants:** Alternate at least three visible-Chrome control and
  candidate runs while freezing the product builds and browsed corpus independently.
  Separate server, transfer and decode, diff mount, useful-ready paint, and continuity
  costs. Evaluate all-visible-row prefetch from measured payload volume rather than
  adding it speculatively.
- **Acceptance:** Candidate blank frames are zero.
  A target speed claim requires nonoverlapping ranges; overlapping cold ranges are
  reported as no detected difference.
  Long work, page exceptions, retained heap, and mounted resources do not regress.
  Manual browser coverage includes rapid pointer and keyboard traversal, direct and
  invalid routes, recovery, small and large comparisons, fold state, unified and split
  layouts, both themes, and reduced motion.
  Focused tests, `make format`, and `make verify` pass.

### Phase 5: Enforce Navigational-Row Keyboard Parity (`mb-xmkn`)

- **Files and functions:** Add focused-row helpers beside `appendRows`, `renderRow`, and
  `selectCommit` in `git-panel.js`. Extend the fake focus and event model plus row cases
  in `tests/dom/git-panel-behavior.js`. State the shared contract in
  `docs/design-system.md` and maintain the surface registry in
  `tests/test_design_vocabulary.py`.
- **Behavior and invariants:** A mounted Git history contributes exactly one Tab stop.
  Unmodified Arrow Up and Arrow Down focus and open the adjacent mounted commit through
  `selectCommit`, allow repeat, prevent page scrolling, and clamp without reopening at
  either edge. Click, Enter, Space, pointer and focus preparation, append-only paging,
  stale-selection checks, and direct routes retain their behavior.
  Selection updates the roving anchor and `aria-current` without forcing pointer focus.
- **Acceptance:** Focused tests prove the prior all-tabbable behavior fails, then cover
  both directions, repeat, modifier exclusion, boundary clamping, focus, selection,
  scrolling, and the design-system registry.
  A visible-browser smoke test traverses a real repository by keyboard before the full
  format and verification gates pass.

### Phase 6: Move the Change Summary (`mb-j0um`)

- **Files and functions:** Add a focused aggregate-summary projection beside
  `renderCommitDetail` in `git-panel.js`; let revision-hosted mounts select a
  summary-free toolbar through `mountDiffView` and `renderDiffToolbar` in
  `builtin_plugins/diff/diff-view.js` and the revision path in
  `builtin_plugins/diff/index.js`. Update the Git header rules in `styles.css` and the
  focused Git and diff DOM suites.
- **Behavior and invariants:** The number of changed files and `+N −N` totals sit with
  the revision, author, and age before the commit body.
  A comparison mounted under a commit omits its lower duplicate but keeps the layout
  control. Direct `.diff` and `.patch` documents retain their normal summary.
  Unknown totals remain visibly unknown, and bounded or estimated data is not presented
  as exact.
- **Acceptance:** Tests prove DOM ordering, exact stat text, and one visible aggregate
  summary per commit surface while preserving the direct diff summary and both layout
  modes. Narrow layouts wrap without obscuring metadata, and both themes retain the
  semantic addition and deletion colors.

### Phase 7: Make the Revision Copyable (`mb-wchz`)

- **Files and functions:** Render a path-like revision group in `renderCommitDetail` in
  `git-panel.js`. Extend the explicit-text copy mode in `plugin-sdk.js`, migrate the
  file header in `app.js` and `renderFileBar` in `builtin_plugins/diff/diff-view.js` to
  that shared delegate, and update `styles.css`, `docs/design-system.md`, the
  copy-delegate, Git-panel and diff-view DOM suites, and the static design checks.
- **Behavior and invariants:** The visible label remains the short revision; the copy
  payload is the full commit ID. Revision and file-path buttons use the same
  icon-button, delegated clipboard, success, failure, and reset behavior, with
  control-specific accessible labels.
  Values ride in escaped data attributes, never inline JavaScript.
  The diff file bar continues excluding its copy button from disclosure activation.
- **Acceptance:** Focused tests cover the full revision payload, icon and accessible
  label, successful and rejected clipboard writes, feedback reset, existing path-copy
  behavior, and the shared design-system vocabulary.
  Pointer, keyboard, and screen-reader operation work in a visible browser.

### Phase 8: Consolidate the Commit Summary Component (`mb-lk26`)

- **Files and functions:** Give `renderCommitSummary` in `git-panel.js` sole ownership
  of the summary markup, keep aggregate projection in `renderCommitChangeStats`, and
  reduce `renderCommitDetail` to composing that component with the comparison and
  bounded-file surfaces.
  Update the component selectors in `styles.css`, the Git-panel DOM suite,
  `docs/design-system.md`, and the static design-vocabulary registry.
- **Behavior and invariants:** One `.git-commit-summary` root contains the subject,
  revision and copy control, author, age, change stats, refs, and optional description
  in that order. The `.git-commit-change-stats` child owns only files, additions, and
  deletions. The comparison, out-of-root files, and bounds remain siblings.
  Escaping, unknown totals, semantic colors, wrapping, copy behavior, and hosted-summary
  suppression remain unchanged.
- **Acceptance:** Focused tests prove that one root owns the complete anatomy and that
  the detail renderer composes it rather than rebuilding fragments.
  A maintained design-system test ties the documented root and child names to the
  renderer and CSS. Focused tests, `make format`, `make verify`, and a visible-browser
  smoke test pass.

### Phase 9: Cancel Obsolete Retained-Diff Work (`mb-k9a5`)

- **Files and functions:** Add `queueDeferredHydration` and a pending-work cancellation
  operation to `mountDiffView` in `builtin_plugins/diff/diff-view.js`; invoke the
  cancellation operation for a different selected revision in `selectCommit` in
  `git-panel.js`. Extend the lifecycle cases in `tests/dom/diff-view-behavior.js` and
  the retained-handoff cases in `tests/dom/git-panel-behavior.js`.
- **Behavior and invariants:** A selected revision keeps the prior diff DOM visible but
  immediately aborts that diff’s active file fetches and syntax waits, disconnects
  queued viewport observations, and clears its timers and yielders.
  Deferred files do not issue requests before their sections intersect the visible
  scroll area, and at most two visible deferred sections hydrate concurrently.
  Cancellation is idempotent and does not remove the root.
  The atomic swap still transfers ownership to the replacement before disposing the
  prior handle; stale selections cannot cancel the replacement.
- **Acceptance:** Focused tests prove that multiple offscreen deferred files issue no
  requests, three intersecting files start only two concurrent requests, and
  cancellation aborts pending work, blocks late DOM mutation, retains the old root, and
  still permits exact final disposal.
  A visible-browser stress pass over a large real comparison keeps the selected row,
  route, and mounted revision convergent without obsolete file-hydration requests
  delaying the selected comparison.
  Focused tests, `make format`, and `make verify` pass.

Chrome 151 validation on an 88-file comparison found 36 deferred sections.
Jumping a 900 px preview to the bottom made 24 sections visible together, which would
otherwise launch 24 Git comparison requests.
Two active requests preserve parallel progress if one file is slow while bounding the
server work a single viewport can start.

### Phase 10: Gate Deferred Request Storms (`mb-bb3y`)

- **Files and functions:** Extend the fetch wrapper, `snapshot`, and `reset` in
  `static/perf.js` with whole-window maximum concurrency and per-request-class maxima.
  Add a deferred-hydration stress phase and pure health validator to
  `explorations/performance-loop/capture-browser.js`. Cover the recorder and validator
  in `tests/dom/perf-behavior.js` and `tests/test_browser_performance_capture.py`;
  update the performance framework, loop guide, plan, and changelog.
- **Behavior and invariants:** The headed `git-revisions` scenario finds a revision with
  at least three deferred files in its real corpus, resets the profiler, scrolls until
  file hydration is active, and selects an adjacent revision.
  Deferred requests never exceed two in flight.
  Active old-revision requests abort; none completes successfully after selection.
  The selected row, commit route, and rendered revision converge with one mounted
  comparison. A corpus that cannot exercise deferred and queued work fails the scenario
  rather than producing a false pass.
- **Acceptance:** Focused tests fail before and pass after the new signals and
  validator. A fresh-origin, headed Chrome run exercises a large comparison, records the
  bounded maximum and cancellation, and exits nonzero when any invariant is violated.
  `make format` and `make verify` pass.

### Phase 11: Deliver and Monitor (`mb-j8ni`)

- **Files and functions:** Review the complete branch diff and PR metadata, keep the
  performance follow-up PR aligned with the implemented scope, and use the original
  review channel for every finding disposition.
  This phase makes no product-code change unless review or CI finds a defect.
- **Behavior and invariants:** The exact pushed head receives another headed Git
  scenario run. Formal reviews, inline comments, general comments, linked issues,
  in-repository review documents, and required CI are all audited.
  The performance follow-up remains stacked on the syntax follow-up for a focused diff;
  after the base lands, retarget the performance PR to `main` without losing its
  implementation commits.
- **Acceptance:** Every actionable finding has a fixed, rebutted, or deferred
  disposition, the exact head passes GitHub CI, `make format`, `make verify`, and the
  real-browser scenario, and the branch is clean and pushed.
  Close `mb-j8ni` and epic `mb-fgcg` only after those conditions hold, then run
  `tbd sync`.

## Measured Result

Three interleaved visible-Chrome runs froze both products and the browsed repository:
control product `4c995e2`, candidate product `00265ed`, and one detached corpus at
`4c995e2`.

| Measure | Control Median (Range) | Candidate Median (Range) | Result |
| --- | ---: | ---: | --- |
| Pointer-prepared transition | 209.7 ms (205.8–245.0) | 104.4 ms (99.6–109.2) | 105.3 ms faster; ranges do not overlap |
| Blank frames per scenario | 4 (4–5) | 0 | Eliminated |
| First cold transition | 225.2 ms (219.0–230.1) | 214.2 ms (204.7–225.2) | No detected difference |
| Second cold transition | 444.8 ms (419.5–476.8) | 383.3 ms (383.1–425.4) | No detected difference |
| Maximum Long Task | 148 ms (146–177) | 132 ms (126–134) | Lower; ranges do not overlap |
| Retained heap after GC | 7.0 MB (7.0–7.1) | 7.0 MB (7.0–7.1) | Unchanged |

The prepared candidate issues no request after the click.
Cold comparison requests are primarily server work, while mounting a heavy diff is a
separate 153–168 ms client cost; the concurrent path overlaps them but its three-run
ranges still overlap the control.
Every candidate scenario ends on the exact selected revision with one mounted diff and
zero page exceptions.
See
[exp-018](../../../../explorations/performance-loop/experiments/exp-018-git-revisions-swap-without-blanking.md)
for the complete record and caveats.

## Testing Strategy

The fake-DOM Git panel suite pins request sharing, ordering, stale-operation behavior,
preview continuity, accessibility state, retained-work cancellation, exact disposal,
commit-header ordering, and the full revision copy payload.
Diff plugin tests verify that prepared and fetched documents follow the same validation
and mount path and that only direct diff documents retain the toolbar summary.
Copy delegate and static design tests pin clipboard feedback, tokenized transitions, and
reduced-motion behavior.

The CDP scenario provides end-to-end evidence on the repository itself.
Its large-comparison phase fails on deferred-request fanout, missing cancellation,
obsolete successful completions, selection/route/render divergence, or multiple mounted
comparisons. Manual real-browser validation covers fast repeated pointer and keyboard
navigation, error recovery, direct commit routes, large and small comparisons, fold
controls, split and unified layouts, theme contrast, and absence of flicker.

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
