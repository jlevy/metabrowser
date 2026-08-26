---
title: Git Revision Navigation Performance
description: Measured plan for fast, stable transitions between commit comparisons in the Git history view
author: Joshua Levy (github.com/jlevy) with LLM assistance
---
# Feature: Git Revision Navigation Performance

**Date:** 2026-08-25 (last updated 2026-08-25)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Implemented and locally validated; PR handoff in progress

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
Git history rows also project the selected commit summary into a compact tooltip instead
of repeating the complete commit description as an unstructured block.
The final phase extends the same continuity rule to ordinary file navigation: retained
content dims immediately, each selected view owns a measurable painted-readiness
boundary, and the performance loop tests file and Git transitions separately without
pretending that their renderer lifecycles are identical.

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
- Reuse the commit-summary vocabulary in a bounded row tooltip with subject, author,
  revision identity, age, and aggregate change counts, without making the tooltip an
  interactive surface
- Give retained file and Git previews the same immediate, subtle pending feedback and
  claim-owned accessibility state
- Measure ordinary file selection through active-view readiness and a double-frame
  painted boundary instead of stopping when the response envelope or container arrives
- Add a trusted regular-file navigation scenario that fails on blank frames, stale
  path/render state, stuck pending state, missing attribution, or duplicate active
  mounts
- Preserve route ownership, rapid-selection correctness, plugin disposal, keyboard and
  pointer behavior, and reduced-motion preferences

## Non-Goals

- Prefetching comparison data for every visible history row
- Changing Git history pagination or virtualization; the
  [unbounded Git history plan](plan-2026-08-25-unbounded-virtualized-git-history.md)
  owns those concerns
- Adding a server cache before measurements show that server computation dominates
- Hiding latency with decorative motion or introducing a new animation library
- Requiring arbitrary file plugins to render in a detached container; connected layout
  remains part of the existing renderer contract
- Adding adjacent-file prefetch or another cache before repeated measurements isolate a
  cost that it would address
- Changing comparison semantics, diff highlighting, or requiring an incompatible public
  plugin SDK change

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

The existing file-selection path retains the prior file only during the response and
asset-loading envelope.
After 120 ms it disposes that view and replaces it with a spinner; after installing the
next file shell, it can report selection complete before an asynchronous active plugin
or the next painted frame is ready.
The Git path instead stages its complete replacement off-DOM and swaps only after the
comparison mount. The final implementation keeps that ownership difference, but gives
both paths the same pending vocabulary and the same observable definition of useful
readiness.

## Design

### Revision Preparation

`git-panel.js` represents preparation as one revision-scoped operation containing:

- the bounded commit-detail request
- eager acquisition of the already registered or on-demand diff assets
- one comparison-data promise from the diff plugin’s existing data hook

Selection starts all independent work together.
Pointer entry and unselected keyboard focus wait for the same stable-intent interval as
the hover card before starting speculative detail and comparison work.
A click or Arrow-key selection starts immediately and may reuse preparation that already
crossed that boundary.
This keeps fast pointer traversal and scrolling network-free while an intentional pause
still prepares the likely selection.
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
The preview immediately receives a lightweight pending state and `aria-busy="true"`; it
is not replaced by a spinner.
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

### Cross-Surface Pending and Readiness

The Git and ordinary file paths share a shell-owned pending lifecycle, not one rendering
algorithm. Starting a selection against useful retained content immediately applies one
tokenized translucent neutral sheet and `aria-busy="true"` under the new preview claim.
The content keeps its geometry and remains available while work proceeds.
Success, failure, stale ownership, preview replacement, and disposal all clear the state
only for the claim that created it.
Reduced motion removes the sheet’s opacity transition, not the immediate state change.
An initial empty preview may still use the existing delayed neutral spinner.

Git keeps its detached atomic handoff because the shell owns the complete commit and
comparison surface. Ordinary plugins keep their connected-container contract because a
renderer may require live layout, observers, or focus state.
The shell installs the next file surface in the connected preview, awaits the active
renderer’s direct promise and an optional instance `ready` promise, then waits for a
double-animation-frame boundary before it clears pending state.
Inactive tabs stay lazy.
A stale or disposed async mount must release any late handle and may not regain
ownership.

The optional `ready` handle is progressive enhancement for a concrete initial-render
boundary. Synchronous renderers and existing instance handles need no change.
Built-in renderers whose direct return currently precedes a known initial asynchronous
pass expose that pass through `ready`; work that intentionally continues after useful
readiness remains outside it.

### Performance Attribution

Production instrumentation adds revision-scoped measures for:

- immediate selection feedback: pending-sheet activation, route ownership, and the old
  and new row mutations
- commit-detail data readiness, including JSON decoding
- diff-asset readiness
- comparison-data readiness, including JSON decoding
- commit markup and diff mounting
- selection to the first painted ready frame

The profiler also retains the maximum simultaneous application fetches for the current
measurement window and per request class.
Query values are excluded from request-class keys, except that deferred file hydration
is distinct from its comparison-manifest request.
The distinction lets the Git scenario enforce the renderer’s two-request hydration bound
without treating the selected revision’s metadata and manifest requests as deferred
fanout. `gitRevision:selectionFeedback` isolates the synchronous main-thread
acknowledgement; `gitRevision:selectToReady` retains the end-to-end boundary, and Event
Timing remains the interaction-to-next-paint signal.

Ordinary file navigation uses parallel phase labels for response-envelope decoding,
selected-kind assets, active-view mounting, optional instance readiness, and selection
to the same double-frame painted boundary.
Labels carry only bounded path, kind, and view metadata.
The selection total must not finish merely because the file shell was inserted or
because a renderer returned a handle whose declared initial work is still pending.

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

A separate trusted `file-views` scenario warms a regular source view, traverses cold
source and Markdown views, and revisits a cached subject.
Each transition proves exact selected path, route, active view, and painted content
convergence; continuous retained content; immediate pending onset and eventual
clearance; one active mounted owner; and complete server, transfer/decode, assets,
mount, paint, Long Task, Long Animation Frame, and exception attribution.
It uses the same acceptance vocabulary as `git-revisions` while retaining its own schema
and subject-specific validators.

### API and Compatibility

No server route or external dependency changes.
The server, shell, and built-in diff plugin ship together, so passing prepared
comparison data through the existing internal render context is an atomic internal
change. No compatibility layer is needed.
An optional `ready` promise on a renderer instance handle is additive: existing plugins
may continue returning nothing, a direct handle, or a promise for either.
No renderer is forced into detached mounting, and no fallback compatibility branch is
introduced.

## Implementation Plan

Epic `mb-fgcg` owns this plan.
Its twenty-two child beads separate measurement, behavior, presentation, validation,
keyboard consistency, commit-header information design, component ownership,
retained-work cancellation, cross-surface pending and readiness parity, and delivery.
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
| Cancel obsolete retained-diff work | `mb-k9a5` | `mb-32kx` | Closed |
| Gate deferred request storms | `mb-bb3y` | `mb-k9a5` | Closed |
| Render bounded commit-summary tooltips | `mb-3j4g` | `mb-lk26` | Closed |
| Audit preview handoff and readiness parity | `mb-b83r` | None | Closed |
| Share immediate dimmed preview feedback | `mb-2yd5` | `mb-b83r` | Closed |
| Measure painted readiness for regular file views | `mb-m23h` | `mb-b83r` | Closed |
| Gate regular file navigation in the performance loop | `mb-wf52` | `mb-2yd5`, `mb-m23h` | Closed |
| Deduplicate selected and prefetched file requests | `mb-v4qu` | `mb-wf52` | Closed |
| Validate preview transition parity | `mb-eh0n` | `mb-2yd5`, `mb-m23h`, `mb-wf52`, `mb-v4qu` | Open |
| Make retained preview dimming visibly cover the main view | `mb-rnr7` | None | Closed |
| Delay Git hover preparation until stable intent | `mb-ues1` | None | Closed |
| Gate Git pending timing and row-anchor attribution | `mb-f43i` | None | Closed |
| Standardize retained-navigation interaction attribution | `mb-1xm2` | `mb-f43i` | Closed |
| Complete the PR and CI handoff | `mb-j8ni` | `mb-eh0n`, `mb-rnr7`, `mb-ues1`, `mb-1xm2`, and completed prior phases | Blocked |

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

### Phase 11: Render Bounded Commit-Summary Tooltips (`mb-3j4g`)

- **Files and functions:** Extend `renderCommitSummary` and `renderCommitChangeStats` in
  `static/git-panel.js` with one compact projection for `scheduleHover` and
  `cancelHover`. Add the modifier styles in `static/styles.css` and focused contracts in
  `tests/dom/git-panel-behavior.js` and `tests/test_design_vocabulary.py`. Reconcile the
  design system and changelog.
- **Behavior and invariants:** Hovering or focusing a history row shows subject, author,
  short revision with the familiar copy glyph, age, changed-file count, additions, and
  deletions through the shared tooltip controller.
  The tooltip omits the commit body and refs, clamps the subject to a small fixed line
  count, escapes all content, preserves unknown totals, and remains supplementary and
  noninteractive. The actual copy button remains in the selected commit summary.
  Pointer and keyboard intent share cached detail preparation, and leaving one modality
  does not dismiss the tooltip while the other still owns the row.
- **Acceptance:** Focused tests fail before and pass after the compact projection and
  hover/focus lifecycle.
  A maintained design-system test binds the documented modifier, renderer, and styles.
  Real-browser checks cover long messages, unknown totals, hover, focus, dismissal, both
  themes, and unchanged row selection and revision-copy behavior.
  `make format` and `make verify` pass.

### Phase 12: Audit Preview Handoff and Readiness (`mb-b83r`)

- **Files and functions:** Inspect `claimPreview`, `selectFile`, `renderFile`,
  `mountPluginView`, and the shell preview bridge in `static/app.js`; `selectCommit`,
  `renderCommitDetail`, and `mountCommitDiff` in `static/git-panel.js`; and the renderer
  lifecycle in `docs/plugins.md`. Record the result in this plan and the bead graph.
- **Behavior and invariants:** Git owns a complete commit-comparison surface and may
  stage it detached before one atomic replacement.
  Ordinary plugin views mount in a connected preview and may depend on live layout or
  complete asynchronous work after their direct return.
  Both paths need claim-owned pending state and painted readiness, but neither path
  changes ownership merely to resemble the other.
- **Acceptance:** The plan names exact lifecycle seams, current measurement gaps, common
  vocabulary, and deliberate differences.
  The implementation graph contains no generic off-DOM adapter, speculative cache,
  compatibility branch, or duplicate bead.
  `tbd sync` succeeds.

### Phase 13: Share Immediate Dimmed Feedback (`mb-2yd5`)

- **Files and functions:** Add `beginPreviewNavigation` and `endPreviewNavigation`
  beside `claimPreview`, `renderPreviewHtml`, and `renderPreviewNode` in
  `static/app.js`; expose the lifecycle through `MetabrowserShell` in
  `static/types.d.ts`; use it from `selectFile` and `selectCommit`; replace the Git-only
  pending modifier with one shared rule in `static/styles.css`. Update focused shell and
  Git DOM tests, `docs/design-system.md`, and `CHANGELOG.md`.
- **Behavior and invariants:** Selecting from useful retained content immediately dims
  the preview under one tokenized translucent neutral sheet, then sets
  `aria-busy="true"`. The sheet does not filter or restyle the rendered document.
  The state retains geometry, does not block interaction, has no progress bar or minimum
  duration, and clears only for its owning preview claim after success, error,
  replacement, cancellation, or tab ownership change.
  Empty initial loads keep the delayed neutral spinner.
  Reduced motion disables the transition while preserving the state change.
- **Acceptance:** Focused tests fail before and pass after for file and Git selection,
  rapid replacement, stale cleanup, errors, and initial empty loads.
  One class and shell lifecycle own both paths.
  Visible checks cover both themes and reduced motion without a blank frame or stuck dim
  state.

### Phase 14: Measure Regular-File Painted Readiness (`mb-m23h`)

- **Files and functions:** Make `measureNextPaint`, `selectFile`,
  `renderFileWithPlugins`, `renderFile`, and `mountPluginView` in `static/app.js` expose
  one awaitable active-view boundary.
  Define an optional renderer-instance `ready` promise in `static/types.d.ts` and
  `docs/plugins.md`. Add it to the built-in Markdown and folder renderers only where
  their direct return currently precedes a concrete initial asynchronous pass.
  Update lifecycle, type, and loading-delay tests.
- **Behavior and invariants:** File selection measures response-envelope decode,
  selected-kind assets, connected active-view mount, optional instance readiness, and
  selection-to-double-frame painted readiness.
  Awaiting an active mount preserves idempotent disposal, cleans up late handles, and
  cannot let stale work regain preview ownership.
  Synchronous views remain immediate, existing plugins need not expose `ready`, inactive
  tabs stay lazy, and arbitrary renderers remain connected.
- **Acceptance:** Focused tests prove selection cannot report useful-ready before a
  direct async render or declared `ready` pass settles; synchronous and rejected paths
  remain correct; stale and disposed mounts cannot leak a handle or mutate the active
  surface; production labels use bounded path, kind, and view metadata.

### Phase 15: Gate Regular-File Navigation (`mb-wf52`)

- **Files and functions:** Add trusted file-row dispatch, exact file/view convergence,
  retained-preview monitoring, transition measurement, validation, and
  `runFileViewScenario` to `explorations/performance-loop/capture-browser.js`. Expose
  `--scenario file-views` through `run.py`. Update the pure capture tests, performance
  loop guide, and `docs/web-performance-framework.md`.
- **Behavior and invariants:** The headed scenario warms a regular source view, visits
  cold source and Markdown views, and revisits a cached subject through trusted input.
  It records exact selected path, route, active view, and painted content; blank frames;
  pending onset and clearance; total, server, decode, assets, mount, ready, and paint
  phases; payload; Long Tasks; Long Animation Frames; exceptions; and mounted ownership.
  It fails on stale convergence, a blank retained surface, stuck pending state, missing
  attribution, duplicate active mounts, or an uncaught exception.
- **Acceptance:** Pure contract and validator tests fail before and pass after.
  A fixed-corpus headed run emits the new schema, exercises both cold and cached paths,
  and separates server, transfer/decode, assets, mount/readiness, and paint cost without
  changing the initial-load or Git scenario schemas.

### Phase 16: Deduplicate Selected and Prefetched File Requests (`mb-v4qu`)

- **Files and functions:** Reconcile `hoverPrefetchTimer`, `hoverPrefetchPath`,
  `hoverPrefetchController`, `startHoverPrefetch`, `abortHoverPrefetch`, and
  `selectFile` through one join-or-cancel helper in `static/app.js`. Add the exact
  matching-request gate to `measureFileTransition` and `assertFileTransitionHealth` in
  the performance driver.
  Update focused navigation and scenario tests, this plan, and `CHANGELOG.md`.
- **Behavior and invariants:** A selection cancels a matching hover timer that has not
  started, joins a matching prefetch already in flight, and aborts unrelated speculative
  work. After a joined success it renders from the populated cache; after a failed
  prefetch it issues one selected request.
  A stale selection cannot regain route or preview ownership.
  Cold transitions issue at most one matching `/api/file` request; cached revisits issue
  none.
- **Acceptance:** The scenario fails against the measured two-request race.
  Focused tests prove the timer, in-flight, unrelated, failure, and stale-selection
  paths. A headed fixed-corpus rerun records one request for each cold source and
  Markdown transition, zero for the cached revisit, zero blank frames, exact
  convergence, and no page exception.

### Phase 17: Validate Parity and Choose Measured Follow-ups (`mb-eh0n`)

- **Files and functions:** Reconcile focused lifecycle tests, both headed scenarios,
  this plan, `docs/design-system.md`, `docs/plugins.md`,
  `docs/web-performance-framework.md`, the performance-loop guide, `CHANGELOG.md`, and
  the pull request metadata.
- **Behavior and invariants:** Validate cached, cold, error, and rapid-replacement paths
  for ordinary source, Markdown, direct diff documents, and commit comparisons.
  Cover both themes and reduced motion.
  Require exact route, selection, rendered subject, active-view, pending-state, and
  mount convergence with continuous useful content.
  Compare phase attribution before proposing prefetch, caching, or another optimization;
  track any evidence-backed follow-up in a separate bead.
- **Acceptance:** Focused tests, `make format`, and `make verify` pass.
  Both headed scenarios pass against the exact commit.
  Documentation describes the shared user contract and the deliberate
  connected-versus-detached lifecycle difference, and the PR validation plan gives a
  zero-context reviewer the evidence needed to reproduce it.

### Phase 18: Make Pending Feedback Unmistakable (`mb-rnr7`)

- **Files and functions:** Refine the shared `.preview-navigation-pending` rules and
  component tokens in `static/styles.css`; update
  `test_shell_shares_immediate_claim_owned_preview_feedback` in
  `tests/test_browser_loading_delay.py`, this plan, `docs/design-system.md`, and
  `CHANGELOG.md`.
- **Behavior and invariants:** One fixed, pointer-transparent sheet covers the visible
  main-view scrollport as soon as a retained navigation begins.
  It does not filter or restyle the syntax-highlighted or diff DOM below it.
  The nav panel remains at full contrast, geometry stays fixed, pointer input stays
  available, and the owning preview claim clears the state only after painted readiness.
  A dedicated 60 ms ease-out reaches the neutral treatment materially faster than the
  general 150 ms control transition.
  Reduced motion removes the interpolation but not the visible state.
- **Acceptance:** Focused tests pin the shared overlay token, fixed scrollport geometry,
  pointer transparency, opacity transition, and reduced-motion behavior.
  Real-browser checks cover both themes, a scrolled diff, rapid replacement, and
  pending-state clearance.

### Phase 19: Keep Scroll-Through Hover Network-Free (`mb-ues1`)

- **Files and functions:** Change `scheduleHover` and its interaction with
  `prepareRevision` and `cancelHover`, and make `setCommitRowAnchor`,
  `moveCommitRowFocus`, and `selectCommit` mutate only the previous and selected rows in
  `static/git-panel.js`. Extend `measureGitTransition` and add
  `assertGitTransitionHealth` in `explorations/performance-loop/capture-browser.js`.
  Extend the preparation and tooltip cases in `tests/dom/git-panel-behavior.js`, the
  maintained design contract in `tests/test_design_vocabulary.py`, and the performance
  driver contract in `tests/test_browser_performance_capture.py`; update this plan,
  `docs/design-system.md`, `docs/web-performance-framework.md`, the performance-loop
  README, and `CHANGELOG.md`.
- **Behavior and invariants:** Entering a row schedules but does not start speculative
  commit-detail or comparison work.
  Leaving before stable intent cancels the timer with zero requests.
  A stable hover or focus starts one bounded preparation, while click and Arrow-key
  selection still update row, scroll position, route, and pending feedback immediately
  and reuse matching work without duplication.
  Interaction-time selection updates touch only the old and new rows, regardless of
  mounted history length.
  Git row backgrounds change without a transition so the visible selection does not ease
  in behind the input.
  The new row is already focused and programmatically focusable; its one-row Tab anchor
  finalizes after painted readiness so focus-order recalculation across a large retained
  diff does not block the input task.
  The synchronous block is measured as `gitRevision:selectionFeedback`, separately from
  the existing selection-to-painted-ready span and browser Event Timing.
- **Acceptance:** Focused tests fail before and pass after for rapid enter/leave, stable
  intent, selected reuse, replacement abort, request counts, tooltip lifecycle, and the
  absence of collection-wide interaction mutations.
  Every headed transition records the selection-feedback, painted-ready, and row-anchor
  phase labels, observes ordered pending onset and clearance timing, and fails on a
  stale selected row, route, rendered revision, stuck busy state, blank frame, or
  multiple mounted comparison.
  A headed scroll-through check confirms that transient rows issue no detail or
  comparison requests and that the selected row and pending main view update without
  waiting for the replacement diff.

### Phase 20: Standardize Interaction Attribution (`mb-1xm2`)

- **Files and functions:** Reconcile the stateful-navigation procedure and metric table
  in `explorations/performance-loop/README.md`, the maintained contract in
  `docs/web-performance-framework.md`, the follow-up evidence in
  `explorations/performance-loop/experiments/exp-018-git-revisions-swap-without-blanking.md`,
  this implementation map, and `CHANGELOG.md`. Confirm that `measureGitTransition` and
  `assertGitTransitionHealth` in `capture-browser.js` and their focused contract tests
  enforce the documented phase, pending, continuity, convergence, and request gates.
- **Behavior and invariants:** The standard procedure freezes build, corpus, subjects,
  viewport, and foreground visibility; repeats captures; separates synchronous
  acknowledgement, complete painted readiness, and Event Timing; treats pending
  mutations as state-onset rather than paint proof; audits the complete input task when
  clocks disagree; and correlates finite application phases with Long Tasks and Long
  Animation Frame forced-layout attribution.
  Conclusions retain unresolved costs rather than broadening a local improvement claim.
- **Acceptance:** Durable guidance links to one authoritative procedure instead of
  duplicating it. The experiment records the focus-handler attribution finding and
  repeated evidence. Existing scenario tests prove that missing phases, pending timing,
  continuity, convergence, request bounds, or cancellation health fail closed.
  Documentation tests, focused performance tests, `make format`, and `make verify` pass.

### Phase 21: Deliver and Monitor (`mb-j8ni`)

- **Files and functions:** Review the complete branch diff and PR metadata, keep the
  performance follow-up PR aligned with the implemented scope, and use the original
  review channel for every finding disposition.
  This phase makes no product-code change unless review or CI finds a defect.
- **Behavior and invariants:** The exact pushed head receives both headed navigation
  scenario runs. Formal reviews, inline comments, general comments, linked issues,
  in-repository review documents, and required CI are all audited.
  The performance follow-up remains stacked on the syntax follow-up for a focused diff;
  after the base lands, retarget the performance PR to `main` without losing its
  implementation commits.
- **Acceptance:** Every actionable finding has a fixed, rebutted, or deferred
  disposition, the exact head passes GitHub CI, `make format`, `make verify`, and the
  real-browser scenarios, and the branch is clean and pushed.
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

The first headed `file-views` validation on a settled fixed project corpus found a real
prefetch interaction defect: cold source selection issued two identical `/api/file`
requests. The selected request ran for about 454 ms; the 250 ms row-hover timer then
started a duplicate that ran for about 208 ms, and both completed together.
This is a single diagnostic reproduction, not a comparative speed claim.

After selection began canceling an unstarted matching timer or joining matching
in-flight work, the same fixed-corpus gate recorded:

| Transition | Total | Matching File Requests | Blank Frames | Pending Onset / Clear |
| --- | ---: | ---: | ---: | ---: |
| Cold source | 104.5 ms | 1 | 0 | 35.6 / 99.6 ms |
| Cold Markdown | 87.2 ms | 1 | 0 | 16.5 / 86.6 ms |
| Cached source | 84.8 ms | 0 | 0 | 22.7 / 82.4 ms |

Every transition converged on the exact selected row, route, rendered path, active view,
and one mounted plugin container, with `aria-busy` and the shared pending state cleared
and zero page exceptions.
The profiler recorded envelope decoding, selected-kind assets, active-view readiness,
and painted readiness separately.
These one-run values validate the scenario and the request-count fix; any broader
performance claim still requires interleaved repeated captures.

A later settled headed Git capture on fixed corpus `tree-a01f4187` isolated a cold
267–398 ms forced-layout interval to changing the newly focused row from `tabindex="-1"`
to `tabindex="0"` while a large diff remained mounted.
Lookup, selected state, pending state, route state, and the internal anchor marker each
measured 0–4 ms. After both the selection path and its synchronous focus handler stopped
changing the Tab anchor before paint, three repeated settled captures recorded
selection-feedback spans of 0.3–4.6 ms, pending onset at 7.7–18.8 ms, and separate
post-readiness anchor spans of 0.5–7.9 ms.
Maximum forced style and layout time was zero in all three runs.
Every transition retained useful content, cleared its pending state, and converged
exactly, with zero blank frames, at most two deferred file requests, zero obsolete
successes, and zero page exceptions.
Event Timing still recorded 344–456 ms maxima and the longest tasks were 326–434 ms,
principally around cold comparison data and rendering; those remain visible follow-up
costs rather than being misreported as solved input-handler work.
This is repeated attribution and acceptance evidence, not a comparative speed claim.

## Testing Strategy

The shell and plugin lifecycle suites pin preview-claim ownership, immediate shared
pending state, direct and instance-declared async readiness, stale late-handle cleanup,
exact disposal, and the double-frame ready boundary.
The fake-DOM Git panel suite pins request sharing, ordering, stale-operation behavior,
preview continuity, accessibility state, retained-work cancellation, commit-header
ordering, compact tooltip projection and lifecycle, and the full revision copy payload.
Diff plugin tests verify that prepared and fetched documents follow the same validation
and mount path and that only direct diff documents retain the toolbar summary.
Copy delegate and static design tests pin clipboard feedback, tokenized transitions, and
reduced-motion behavior.

The two CDP scenarios provide separate end-to-end evidence for Git and regular-file
navigation on the repository itself.
The Git scenario’s large-comparison phase fails on deferred-request fanout, missing
cancellation, obsolete successful completions, selection/route/render divergence, or
multiple mounted comparisons.
Each ordinary Git transition also fails on a blank retained surface, missing or stuck
pending feedback, missing immediate or painted-ready phase attribution, or
selection/route/render divergence.
The file scenario fails on blank retained content, route/path/view divergence, stuck
pending state, missing painted-readiness attribution, or duplicate active mounts.
Manual real-browser validation covers fast repeated pointer and keyboard navigation,
cached and cold source and Markdown files, error recovery, direct commit routes, large
and small comparisons, fold controls, split and unified layouts, both themes, reduced
motion, and absence of flicker.

## Rollout Plan

The shell and built-in plugins ship as one artifact.
Land the complete client, plugin, scenarios, tests, experiment, and documentation change
together. No feature flag or data migration is required.
The optional renderer-instance readiness promise is additive and does not require a
compatibility layer.

## Open Questions

None. Further server caching, adjacent-row background prefetching, file prefetching, or
another paint optimization requires repeated phase attribution and a separate bead that
names the measured bottleneck.

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
