# Feature: Functional UI and CLI Parity

**Date:** 2026-09-10 (last updated 2026-09-10)

**Author:** Joshua Levy (with LLM assistance)

**Status:** In Review

## Overview

Every functional behavior a user can observe in Metabrowser should have deterministic
evidence that runs from a command line without opening a browser.
The existing parity rule covers routes, kinds, and models, then exempts the entire view
layer. That exemption is too broad: it allowed the Recent panel to report a count from
the complete provider result while deciding folder membership from only the rows mounted
in the DOM.

This plan narrows the boundary.
Data semantics belong to a route or model reached by `metab`; browser-owned interaction
semantics run through the exact production JavaScript in a browserless golden session;
only paint and platform behavior may be exempt, with a specific reason and focused
browser evidence.

## Goals

- Make Recent filtering correct when matching descendants are cached under collapsed
  folders or lie beyond a rendered page.
- Put membership, ordering, counts, bounds, and truncation before rendering and expose
  the same answer through `metab --api`.
- Make Recent converge after deep changes, reconnects, capped-page removals, and window
  expiry without retaining an unbounded overlay or issuing one provider scan per event.
- Add one deterministic, composed golden session that exercises the production request
  model, Recent tree model, and live-repair state machine without a browser.
- Restore Markdown TOC fragment binding and current-section tracking in hosts that do
  not provide `IntersectionObserver`, with the exact KPress module in the session.
- Make functional UI parity a checked registry rather than an unenforced sentence.
- Keep the fast test path representative enough that routine work does not require a
  browser for semantic validation.

## Non-Goals

- Reproduce CSS layout, paint, animation, font metrics, or browser engine behavior in a
  command-line harness.
- Build a general-purpose fake DOM or add a DOM dependency.
- Publish `/api/*` as a compatibility contract.
  The shell, server, and built-in plugins continue to ship and change together.
- Replace a small number of real-browser checks for inherently visual or platform-owned
  behavior.

## Background

The Past hour regression combines two individually tested features.
`/api/recent` returns the complete bounded set of matching leaves, and `renderTreeNodes`
deliberately keeps descendants of collapsed folders in `subtreeCache` instead of
mounting them. `applyTreeFilters` then passes only mounted `.tree-item` rows to
`clusterHiddenIds`. A collapsed folder therefore appears childless and is hidden even
though its count chip and the panel tally both prove that matching descendants exist.

The route golden did not catch this because both recency cases used fixture mtimes old
enough to return an empty list.
The JavaScript checks did not catch it because the filter model and bounded renderer
were tested in separate sessions against mutually incompatible assumptions.
The failure is in composition, so another isolated unit assertion is not sufficient.

The Markdown regression crossed two integration boundaries in the same way.
Metabrowser rewrote fragment-only TOC links into full `/view/` URLs, while KPress binds
only same-document fragment targets.
The Codex in-app WebView also does not expose `IntersectionObserver`, so even correctly
bound headings had no scroll signal.
KPress and the link enhancer each passed alone; the composed document did not update its
active section.

## Design

### The parity boundary

Every user-visible functional aspect belongs to exactly one of these tiers:

1. **Data semantics.** Membership, ordering, grouping inputs, counts, bounds,
   truncation, persisted state, actions, and recoverable errors are owned by a model or
   route the browser consumes.
   The behavior is reachable through `metab` and pinned by a nontrivial golden
   transcript.
2. **Interaction semantics.** Focus, disclosure, pagination, lifecycle, and other
   browser-owned state machines run in a deterministic CLI session against the exact
   production JavaScript module.
   The golden records the composed behavior; focused invariants explain failures.
3. **Paint and platform behavior.** Geometry, animation, real paint timing, and browser
   APIs may use a real browser.
   Each exemption names the behavior, the reason it cannot be represented honestly in a
   browserless session, and its evidence.

“View layer” is no longer an exemption.
A behavior is exempt only when it belongs to tier 3.

### Recent filtering

`/api/recent` accepts the navigation filter vocabulary in addition to its window and
limit: `types`, `min_size`, and `include_ignored`. The inventory provider applies those
constraints through the same `InventoryFilter` predicate used by `/api/tree`, before
ranking and the response cap.
Its `total_matching` and rows therefore describe the same selection.

The browser serializes the current selection through the shared request model and
refetches Recent when any server-owned dimension changes.
Live filesystem events are still merged between fetches, but the complete leaf list is
filtered before clustering.
Folders are built only from matching leaves and are never pruned from mounted DOM
children.
A renderer may mount, cache, or page descendants without changing which folders
exist.

The live overlay retains at most the route limit.
Shallow filesystem events update that bounded top-N model immediately.
The unscoped catalog event invalidates it for deep or subtree changes that the
depth-bounded filesystem stream cannot describe; a reconnect sentinel and subtractive
changes on a truncated page do the same.
The provider preserves the rare retained file-to-directory or file-to-symlink transition
until that unscoped companion is built, so a deep replacement repairs Recent and removes
the exact Quick File candidate even when navigation originally seated it.
Routine directory aggregate upserts carry no such marker and stay off the catalog wire.
The shared catalog transition also prunes affected retained Recent paths and downgrades
the displayed tally to their recomputed lower bound before the coalesced repair starts.
A shallow path absent from a truncated page has an unknown prior state, so file upserts,
removals, and file-to-directory replacements also trigger repair when they can change
unseen membership. The live tally immediately falls back to the matching rows still
retained locally, a safe lower bound, rather than presenting the previous exact or
provider lower-bound count as current.
One production batch transition owns overlay mutation, subtree pruning, the top-N cap,
the temporary bound, and the repair decision; the shell and golden session invoke that
same transition. Invalidations coalesce into one authoritative repair window, and an
event observed during an HTTP request marks that snapshot dirty so it is replaced once
after it settles.

The Recent clustering transform moves from `app.js` into a small production module.
The shell and the browserless session call the same function.
This is a presentation model, not a second implementation of server filtering.

### Markdown TOC integration

Same-document Markdown links keep their fragment-only authored `href`, which is the
contract KPress uses to associate TOC links with headings.
Metabrowser still retains the resolved navigation target for delegated clicks, history,
and cross-document links.

KPress continues to own TOC selection, disclosure, active-link state, and disposal.
When the host lacks `IntersectionObserver`, a scoped adapter supplies only the missing
observation signal while KPress initializes, then restores the global runtime.
The fallback coalesces scroll bursts through animation frames, selects headings with
logarithmic geometry reads, and removes every listener and pending frame on disposal.

### Checked evidence registry

[Views, Models, and Routes](../../architecture/arch-views-models-routes.md) gains a
functional-aspect table.
Each row names the observable contract, its semantic owner, its command-line golden, and
any focused evidence.
An exemption must be narrowly marked as paint or platform behavior and give a reason.

`devtools/check_parity.py` validates the table, registered route and source owners,
referenced evidence, and executable commands.
It also distinguishes a command in an executable console block from one merely copied
into prose: a functional row names the exact command that demonstrates the behavior.
For interaction rows, the checker runs the exact two-argument Node session with
checker-controlled V8 coverage and credits only canonical production files whose
executed top-level range spans the file’s exact UTF-16 length.
The session cannot grant itself owner credit through stdout or a relabeled source
snippet. Negative tests prove that a missing table, missing owner or evidence file,
prose-only mention, route suffix, failed command, forged filename, or noncanonical
command fails the gate.

The registry is explicit because source scanning cannot discover product semantics.
The checker enumerates registered routes and built-in kinds, while review remains
responsible for declaring the smaller set of observable aspects within each surface.

## Implementation Plan

### Phase 1: Correct Recent and prove the composition

- [x] Write failing provider and route tests for type, filename, size, ignored, count,
  and pre-cap filtering.
- [x] Write a failing browserless session for multiple matching collapsed branches.
- [x] Reuse the provider filter predicate for `/api/tree` and `/api/recent`.
- [x] Send the whole active selection with Recent requests and refetch on every
  server-owned change.
- [x] Filter complete leaves before clustering; remove DOM-descendant membership logic.
- [x] Move Recent clustering into a production module used by both shell and session.
- [x] Bound the live overlay and coalesce authoritative repair after deep changes,
  reconnects, capped-page removals, and expiry.
- [x] Replace the empty Recent route golden with a deterministic nonempty scenario and
  an exact multi-constraint scenario.

### Phase 2: Enforce the narrower parity principle

- [x] Add the functional-aspect registry and its checker.
- [x] Seed it with the navigation filtering, bounded-tree interaction, and explicit
  paint-only rows needed to prove the mechanism.
- [x] Update contributor guidance and end-to-end testing documentation to point to the
  enforced rule.
- [x] Add the regression fixture as the canonical example of a composition session.
- [x] Run the full release gate and review the generated golden diff line by line.

### Phase 3: Restore Markdown TOC composition

- [x] Preserve same-document fragment links while retaining delegated navigation.
- [x] Add a scoped observation fallback for hosts without `IntersectionObserver`.
- [x] Run the link enhancer and KPress’s exact production TOC module over the same
  anchors in one browserless long-document session.
- [x] Pin active-section changes, expand-all state, frame coalescing, native-observer
  preservation, and complete disposal in a golden transcript.
- [x] Reproduce the original long document in the Codex in-app WebView.

### Phase 4: Migrate the existing UI deliberately

- [ ] Inventory existing browser behavior by user-observable contract, not by helper
  file, and classify each contract as data, interaction, or paint/platform.
- [ ] Extract a production controller seam where a source assertion or copied private
  function is the only evidence for cross-module behavior.
- [ ] Promote the strongest existing exact-production Node checks into readable,
  stateful golden sessions and register their functional aspects.
- [ ] Cover shared preview lifecycle, error states, persisted settings, cancellation,
  disposal, and stale-response handling before treating the registry as complete.
- [ ] Maintain a narrow ledger of browser-only evidence for geometry, paint, native
  APIs, image decoding, printing, and performance timing.

The migration is tracked by `mb-n9xg` and its children.
The first three phases establish an enforced release gate for changed behavior; they do
not retroactively prove every legacy interaction.
Until Phase 4 is complete, documentation and release notes must call the functional
registry an enforced seed rather than complete UI coverage.

## Testing Strategy

The provider tests pin one semantic predicate across tree and Recent projections.
Route tests pin query parsing and response counts.
`cli-api-nav.tryscript.md` uses `window=all` with fixed files and mtimes so the
transcript is nonempty and deterministic, then combines type and size constraints across
several folders.

The browserless session runs the exact production filter-control transition, request
launch, response-settlement order, complete-leaf projection, and Recent tree model.
It records the request URL, selected leaf paths, folder paths, folder counts, and
bounded expansion plan for a fixture with several collapsed branches.
The old implementation must fail either because it filters after the response cap or
because a collapsed folder is treated as empty.
The same session runs a real `fs.change` batch and records deep-change invalidation,
reconnect repair, capped-page backfill, fixed-window coalescing, and the retained-map
bound. It passes one deep file-to-directory and file-to-symlink companion through the
production Recent and Quick File models, proving authoritative repair, exact removal of
a navigated stale candidate, an immediate safe Recent tally, and preservation of a
replacement directory’s descendants.

The Markdown session starts from authored same-document TOC anchors and enters through
the exact production rendered-Markdown mount.
That mount runs the production link enhancer before it passes the same nodes to the
installed KPress TOC module through the production observation fallback.
It records the enhanced href and delegated target, active sections at the top, at a
heading, through the middle of a long section, and after a scroll burst.
It then proves that native observation is left untouched and disposal removes scheduled
work and listeners.

Focused tests remain beside the golden so a failure says whether parsing, provider
selection, clustering, or interaction changed.
`make verify` remains the handoff gate.

## Rollout Plan

This is an internal contract change shipped atomically with the browser.
Record the observable fix in `CHANGELOG.md`, install the verified development build with
`uv tool uninstall` followed by `uv tool install`, and reproduce the original fixture
before handing it to the user for parallel testing.

Future user-visible features add or update a functional-aspect row in the same change.
Review enforces that declaration; the checker blocks invalid owners, commands, or
evidence before release.
Existing surfaces migrate through `mb-n9xg`; no new work may increase that inventory
debt.

## Open Questions

None. The route remains the authority for data semantics, production JavaScript remains
the authority for interaction semantics, and paint-only exceptions stay explicit.

## References

- [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)
- [End-to-End Testing](../../../e2e-testing.md)
- [CLI parity and golden coverage](../done/plan-2026-08-21-cli-parity-and-golden-coverage.md)
- `mb-b67v`: Recency filter hides collapsed folders with matching files
- `mb-i22y`: Deep and capped Recent changes must converge through bounded repair
- `mb-8z21`: Markdown TOC scrollspy loses the active section in the in-app WebView

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
