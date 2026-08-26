# Feature: Unbounded Logical Git History with Bounded Rendering

**Date:** 2026-08-25

**Author:** Metabrowser maintainers

**Status:** Draft; targeted for v0.9.0

## Overview

Metabrowser’s Git panel already requests another page near the bottom of the scroll
surface, but it stops after 500 commits.
The cutoff prevents the browser from retaining an ever-growing DOM and graph, yet it
also makes older history inaccessible.
Raising it to 1,000 only moves the same failure.

The v0.9 design removes the numerical history ceiling.
History continues on demand until Git reports its real end.
A virtual list mounts only the visible rows plus a measured overscan window, and a
bounded client page cache retains only the working set.
An opaque server-side history session preserves the ordered Git walk and can replay
evicted pages without making page *N* rerun and discard the first *N - 1* pages.

“Unbounded” describes what the reader can reach, not unlimited use of any one resource.
DOM nodes, retained browser pages, parser buffers, subprocesses, request payloads, and
server sessions all remain bounded.
Temporary session storage may grow with history actually visited; it is released on
expiry or disposal and is never read into memory as one object.

This work begins from the v0.8.0 release, which retains the bounded 500-commit panel.
The complete continuation and virtualization design targets v0.9.0.

## Goals

- Continue loading Git history when the reader nears either edge of the loaded window,
  with no product limit such as 500, 1,000, or 10,000 commits.
- Keep mounted Git rows and their SVG graphs bounded by viewport size and measured
  overscan rather than repository history length.
- Keep retained browser commit data and graph-layout data within a measured working-set
  budget, evicting pages outside it without losing the ability to revisit them.
- Make continuation work per page rather than per accumulated depth.
  Loading a deep page must not repeatedly walk and discard the whole prefix with
  `git log --skip`.
- Preserve the existing default and all-ref scopes, graph lane continuity, selected
  commit, direct `/commit/<revision>` routes, hover details, keyboard access, retry
  behavior, and explicit end-of-history state.
- Measure the browser, Git process, payload, and temporary-storage cost before settling
  page, window, overscan, cache, and session budgets.
- Add structural regression tests so the feature cannot silently return to an
  all-history DOM or a fixed commit cutoff.

## Non-Goals

- Git write operations, live repository updates over SSE, incoming/outgoing summaries,
  or a new branch picker
- A general-purpose virtualization framework for other Metabrowser panels
- A third-party virtualization or Git library
- Native browser find across rows that have not been mounted.
  The panel’s own future history search is separate work.
- Random access to an arbitrary ordinal before Git has identified that part of the
  ordered walk. A direct commit URL remains random access to commit detail, not a promise
  to know that commit’s row number without traversing its scope.
- Hiding operational failures.
  Session expiry, repository changes, subprocess limits, and exhausted temporary storage
  have explicit recovery states rather than presenting a shortened history as complete.

## Background

### Current behavior and cost

The current browser requests 250 commits at a time and keeps every accepted `GitCommit`,
every computed graph row, and every row element.
`GIT_HISTORY_MAX_ROWS` stops that growth at 500 and clears the continuation cursor.
The server cursor contains an opaque skip offset, and every subsequent
`git log --skip=N` walks and discards the prefix again.
`GIT_LOG_MAX_SKIP` bounds that increasingly expensive request shape at 100,000.

An orientation run against this repository produced the following single-browser
observations. These are evidence for the work, not release budgets:

| Loaded history | DOM elements | Serialized panel HTML |
| --- | ---: | ---: |
| 250 commits | 3,608 | 310,616 characters |
| 500 commits | 6,934 | 599,314 characters |

The 250-to-500 scroll fetch and append took 181 ms end to end.
A one-page request with `limit=1000` returned all 584 commits in 202,458 bytes in about
144 ms. Fetching 1,000 commits is therefore plausible in an ordinary repository, but
mounting them is still linear work, and it does not solve a repository with 10,000 or
1,000,000 commits.

At the fixed 22 px row height, Chromium’s measured 33,554,428 px element-height clamp
also appears at roughly 1.5 million rows.
Virtual DOM alone is insufficient for the logical no-limit contract; the scroll
coordinate must be segmented or rebased before that threshold.

### Design constraints

The graph layout is incremental.
Each page begins with the prior page’s trailing lane state and color index, so page
boundaries can be checkpoints.
The renderer does not need every preceding graph row if it can recover the checkpoint at
the start of the current page.

The server, browser shell, and built-in Git panel ship together.
The `/api/git/log` cursor and `METABROWSER_SETTINGS` values are internal contracts, so
v0.9 changes both sides together and removes the old skip cursor rather than adding a
compatibility shim. The observable paging behavior is recorded in `CHANGELOG.md`.

### Complexity assessment

This is medium-high complexity and should be treated as a minor-release feature, not a
larger patch-release tweak.
The work has two independent mechanisms—a replayable Git continuation and a virtualized
graph renderer—followed by an integration phase where scroll anchoring, lane
checkpoints, selection, focus, and expiry recovery interact.
The five-bead sequence keeps measurement ahead of both mechanisms and joins them only
after their structural bounds pass independently.

## Design

### User model

The Git panel remains one continuous chronological graph.
Near the bottom, it loads the next page; after older pages have been evicted, scrolling
upward reloads them.
The panel shows one of four distinct trailing states: loading, retry after a page
failure, real end of history, or session refresh after the underlying history can no
longer be continued.
It never says “showing the newest N commits” unless a real operational error has stopped
the walk.

The selected commit is independent of whether its row is mounted.
Its detail and URL stay in place when its row scrolls out.
Returning to its page restores the selected row style.
A direct `/commit/<revision>` route opens detail immediately; the panel need not walk
from HEAD just to render that detail.
If the revision later appears in the active history scope, its row becomes selected.

### Virtual row window

The list owns a logical range of row ordinals and mounts a fixed-height window around
the viewport. Top and bottom spacers represent unmounted rows within the current scroll
segment. A scroll update computes the desired range, obtains any missing pages, renders
only that range, and disposes row-specific hover state and listeners that leave it.

The existing 22 px row height is the coordinate unit.
Window and overscan sizes are constants exported from `settings.py`; Phase 1 records the
browser measurements beside them.
Tests assert the structural invariant:

```text
mounted rows <= visible row budget + measured overscan budget
```

Once logical height approaches the browser clamp, the panel rebases to another bounded
scroll segment while preserving the apparent row and pixel offset.
Segment rebasing must not move the selected or focused row on screen.
No element receives a height near the browser maximum.

### Bounded browser working set

The client stores a bounded number of decoded pages centered on the virtual window, plus
the selected commit detail in the existing bounded detail cache.
Each cached page contains wire commits and the graph checkpoint needed to lay out its
first row. Rendered SVG nodes and expanded graph-row objects exist only for the mounted
window.

When the cache evicts a page, the panel retains no commit-sized representation of it.
Scrolling back requests it from the same server history session.
Cache eviction is LRU by page access, with adjacent-page prefetch counted inside the
same budget.
The client keeps only a bounded set of neighboring page handles; it does not
build a complete map from ordinal to revision for the whole visited history.

### Server history sessions and cursors

The first log request resolves the requested ref scope once and starts a history
session.
The session owns one ordered `git log` walk, a streaming parser, and a temporary
replay spool. Reading the next page advances that walk once.
Reading a page that the browser evicted reads only that page’s framed records from the
spool. The server never loads the spool or all commits into memory.

The cursor is an opaque token containing the session identity, page identity, direction,
and a scope fingerprint.
It does not expose a caller-controlled skip count.
A session registry bounds concurrent sessions and Git subprocesses, expires idle
entries, and terminates and deletes their resources on eviction or server shutdown.
The exact idle TTL, concurrency, page size, parser buffer, and per-session storage
policy are set from Phase 1 measurements and documented beside their constants.

An operational storage budget may expire a session; it must not masquerade as end of
history. The response distinguishes:

- `400` for a malformed cursor;
- `409` for a scope or repository fingerprint that changed;
- `410` for an expired or evicted history session; and
- `5xx` for a Git or server failure.

The browser can refresh a `409` or `410` session while preserving the selected commit
detail. It reports that the history position must be rebuilt; it does not append a new
walk to stale rows.

The implementation may replace the streaming session with another continuation mechanism
only if Phase 1 demonstrates all of the following: identical `--date-order` output
across merge and multi-ref histories, bounded work per deep page, replay of an evicted
page, stale-scope detection, and no commit-count ceiling.
Plain `--skip` does not meet those criteria.

### Graph checkpoints

The layout result at a page boundary is a checkpoint: trailing swimlanes, palette
cursor, resolved HEAD, ref colors, and the scope fingerprint.
A returned or replayed page carries enough checkpoint data for the browser to compute
that page without every prior graph row.
Checkpoints are versioned as part of the internal response model.

Page boundaries must remain visually continuous in histories with branches, merges,
octopus merges, tags, detached HEAD, and overlapping ref tips.
An invalid checkpoint invalidates the session rather than drawing a plausible but false
graph.

### Focus, selection, and disposal

Rows use roving focus rather than every mounted row having `tabindex=0`. Arrow-key
movement can cross a page boundary and request the adjacent page.
If virtualization unmounts the focused row because of pointer or scrollbar movement,
focus moves to the panel scroller with the logical focused ordinal retained; it returns
to the row when that ordinal mounts again.
Enter and Space keep their current selection behavior.

Unmounting a row cancels its pending hover request and removes its tooltip content.
Replacing or closing the Git panel disconnects scroll observers, ends pending client
requests, disposes a mounted diff, and releases the server history session.
Late responses are ignored by session and render generation.

### Asset loading and compatibility

The work adds no dependency and no new eager asset.
`git-panel.js` and `git-graph.js` remain in their current Git-panel loading tier.
The browser and server change their internal cursor, checkpoint, and settings model in
one release.

Compatibility audit:

| Surface | Decision |
| --- | --- |
| CLI commands and Python library | No change |
| `/api/git/log` cursor and response | Internal coordinated break; update server, browser, validators, tests, architecture map, and changelog together |
| Commit routes | Existing `/commit/<revision>` grammar preserved |
| Plugin SDK and manifests | No change; no SDK version bump |
| Configuration, environment, persisted browser state, database | No released contract affected |

## Implementation Plan

### Phase 1: Measure and freeze structural budgets (`mb-t875`)

- Build deterministic linear, branch-heavy, and merge-heavy repositories at 250, 1,000,
  10,000, and at least one depth that exercises deep continuation.
- Measure response bytes and latency, Git and server RSS, parser buffering, temporary
  bytes per commit, DOM elements, serialized HTML, retained JS heap after collection,
  layout/paint work, scroll tasks, and the browser height clamp.
- Prototype the history-session walk and page replay.
  Reject it or freeze its resource constants against the acceptance criteria above.
- Commit the measurement report and place each chosen constant beside the evidence that
  supports it.

### Phase 2: Scalable continuation (`mb-abu2`)

- Replace skip cursors with the measured session, scope fingerprint, replay spool,
  lifecycle registry, shutdown cleanup, and explicit stale/expired responses.
- Update wire models, runtime validators, routes, settings export, architecture map, and
  changelog as one internal contract change.
- Cover empty repositories, default and all-ref scopes, moving refs, malformed tokens,
  expiry, concurrent panels, resource eviction, and subprocess failure.

### Phase 3: Virtual row window (`mb-ghju`)

- Separate logical pages, graph checkpoints, mounted row models, and DOM ownership.
- Add fixed-height spacers, bounded overscan, page-cache eviction, segment rebasing,
  focus restoration, selection persistence, and complete disposal.
- Keep current row visuals and lane geometry unchanged.

### Phase 4: Integrate continuous scrolling (`mb-vieq`)

- Join bidirectional page loading to the virtual window and recover stale sessions
  without presenting partial history as complete.
- Preserve direct commit routes, hover/detail caching, keyboard boundary movement,
  scope, lane continuity, retry, empty, and real-end states.
- Remove `GIT_HISTORY_MAX_ROWS`, the capped message, and skip-cursor code and tests.

### Phase 5: Validate v0.9 (`mb-0ev5`)

- Run the deterministic structural suite and real-browser profiles at all measured
  sizes, including repeated down/up traversal after cache eviction and a history deep
  enough to force scroll-segment rebasing.
- Compare the release candidate with the preceding release through the performance
  harness, run `make verify`, and record limitations and measurements in the release
  notes.

## Testing and Acceptance

Tests assert structure and behavior, not machine-dependent wall-clock thresholds.

**Server and wire tests** cover exact page order and uniqueness, replay after eviction,
scope isolation, graph checkpoints, stale and expired cursors, bounded parser reads,
session cleanup, malformed input, empty history, and resource failures.
A deep-page test records that continuation does not invoke `git log --skip` or restart
the walk for each page.

**Browser unit tests** cover mounted-row and page-cache upper bounds, spacer geometry,
segment rebasing, adjacent-page prefetch, page eviction and reload, lane continuity,
selection and focus across unmounts, direct routes, hover cancellation, retry and end
states, and lifecycle disposal.
At least one test scrolls past 500 and 1,000 commits and reaches the real final commit.

**Real-browser tests** capture DOM element count, long tasks, serialized panel size,
retained heap after collection, scroll anchoring, request failures, console errors, and
rendered error states.
They traverse down, back up after eviction, and to end on the 10,000-commit corpus.
A separate synthetic logical-depth profile forces segment rebasing without requiring a
million real Git objects in routine CI.

The feature is accepted when:

- a history longer than every former cap reaches its actual final commit;
- mounted rows, client page cache, active requests, session registry, parser buffers,
  and Git subprocesses remain at their measured bounds while traversal depth grows;
- deep continuation work is per page rather than proportional to all preceding pages;
- revisiting an evicted page preserves commit order and graph lanes;
- selection, keyboard focus, direct commit detail, scope, errors, and end-of-history
  behavior pass their regression tests; and
- `make verify` and the v0.9 release comparison pass.

## Rollout

The feature ships as the Git panel behavior in v0.9.0, without a compatibility flag.
The client and server are one artifact, and a flag would double an internal contract
without providing a separately updatable consumer.
If measurement rejects the session prototype, `mb-abu2` remains blocked until a
continuation design meets the same acceptance criteria; the fallback is the honest v0.8
bounded panel, not an unmeasured higher cutoff.

## References

- [Git graph nav panel and Git API](plan-2026-08-06-git-graph-view.md)
- [Rendering large content](../../../large-content-rendering.md)
- [End-to-end testing](../../../e2e-testing.md)
- [Views, models, and routes](../../architecture/arch-views-models-routes.md)
- [Performance loop](../../../../explorations/performance-loop/README.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
