# Feature: Quick File Finder and Search Providers

**Date:** 2026-07-17 (last updated 2026-08-08)

**Author:** Metabrowser maintainers

**Status:** Phase 1 implemented and validated; Phase 2 redefined as the client-complete
catalog feed (decision `mb-ci04`); Phases 3 and 4 planned

## Overview

Metabrowser should open a keyboard-first file finder when the user presses `/`. The
finder fuzzy-matches every file path the browser already knows and opens the selected
file through the existing navigation path.
This first phase is client-only: opening the finder or typing a query does not make a
server request.

The browser intentionally knows less than the server inventory.
The initial event stream contains only the served root through depth two, lazy subtree
responses are held outside `FileStore`, and the Recent panel maintains a separate
bounded result set.
A client-side finder must therefore say when its candidate catalog is
partial. Phase 2 closes the gap from the other side: a minimal catalog feed makes the
client complete over non-gitignored filenames (see “Catalog Feed”), and a later
server-side full-text provider plugs into the same runtime without changing it.

## Goals

- Open a quick file finder with `/` unless focus is in an input, editor, select, or
  content-editable surface
- Fuzzy-match file basenames and served-root-relative paths already observed by the
  browser, with basename matches weighted above parent-path matches
- Search every observed file admitted by the inventory, independent of Current, Recent,
  type, and gitignored filter presentation
- Navigate the result list with the keyboard and open the selected file with the
  existing `navigateToPath` behavior
- Keep one minimal client catalog of paths observed through the Files tree, lazy subtree
  responses, Recent responses, and live inventory events
- Report how many files are locally searchable and whether that catalog is complete
- Define one DOM-independent search runtime and provider contract that can serve the
  palette and a future persistent navigation-panel search box
- Add complete server-side filename search only when the local catalog cannot answer the
  query, without transferring the full inventory to the browser
- Add explicit full-text search as a later server-backed mode with bounded work,
  cancellation, and honest truncation
- Keep startup, initial tree rendering, and direct-file preview independent of search
  readiness

## Non-Goals

- Loading all 500,000 possible inventory entries into the browser at startup
- Running full-text search automatically for every filename query that has no match
- Persisting the finder query or folding it into shared filter preferences
- Replacing the Files tree with search results
- Requiring a database, external search daemon, native extension, or third-party fuzzy
  matching dependency
- Making client-local results appear complete when the browser has only observed part of
  the inventory

## Current State

The browser now implements the client-only Quick File phase over the existing server and
navigation prerequisites.

| Capability | Current State | Consequence |
| --- | --- | --- |
| Server inventory | `InventoryIndex` asynchronously tracks up to 500,000 files at depth 20 and can snapshot `all-known` entries | A server provider can search filenames without another crawl |
| Initial browser inventory | `/api/events?scope=root-depth-2` replaces `FileStore` with entries through depth two | `FileStore` is a partial candidate source, not a complete filename catalog |
| Lazy navigation | `/api/tree` returns the initial tree and lazy subtree responses; direct children are mounted in pages of 200 | Files encountered through navigation are known to the browser even though they are not added to `FileStore` |
| Recent files | `/api/recent` returns up to 2,000 files from the all-known inventory into `recentBaseEntries` | Recent files are another useful bounded candidate source |
| Navigation | `navigateToPath` reveals a tree row when possible and calls `selectFile` even when the row is unmounted | Finder selection can reuse existing preview and route behavior |
| Live updates | Scoped `fs.change` operations update shallow `FileStore` entries | Locally known deep entries can become stale because their changes are outside the event scope |
| Client search | A slash-key palette, known-file catalog, fuzzy matcher, and DOM-independent provider runtime search observed paths without a search request | Phase 1 provides fast navigation but honestly reports partial coverage |
| Server search | No filename or content search route exists | Phases 2 and 3 can add bounded providers without changing the palette or local matcher |

The earlier design treated keyword search as a filtered tree and as a shared filter
dimension.
That couples three distinct tasks: jumping to one file, filtering a hierarchy,
and finding text occurrences.
This plan separates them:

- **Quick file** returns a ranked flat list and opens one path
- **Filter projection** returns a hierarchy and belongs to the unified-filtering plan
- **Full text** returns path and location matches and runs on the server

## Editor Pattern Review

Established editors separate fast navigation from deeper retrieval while reusing a
common quick-input vocabulary:

- VS Code’s [Quick Open](https://code.visualstudio.com/docs/editing/userinterface)
  searches and opens a file by name, while
  [Search across files](https://code.visualstudio.com/docs/editing/codebasics#_search-across-files)
  has a persistent search surface with results grouped by file and location.
  Its
  [Command Palette modes](https://code.visualstudio.com/docs/editing/getting-started#_use-the-command-palette)
  also use explicit prefixes to switch among files, commands, and symbols rather than
  treating every query as the same operation.
- VS Code’s
  [quick-access implementation](https://github.com/microsoft/vscode/blob/main/src/vs/platform/quickinput/browser/pickerQuickAccess.ts)
  combines immediate and delayed picks and cancels an obsolete provider request when the
  input changes. Its
  [Quick Open provider](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/search/browser/anythingQuickAccess.ts)
  caps results, preserves active picks, and scores a label separately from its
  description, while its
  [search service](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/services/search/common/search.ts)
  exposes distinct file-search and text-search queries.
- IntelliJ IDEA’s
  [Search Everywhere](https://www.jetbrains.com/help/idea/searching-everywhere.html)
  uses one popup with explicit file, symbol, action, and text contexts.
  It can show text results when other categories have few or no matches, but it also
  provides a dedicated Find tool window for deeper result inspection.

The Metabrowser design follows the common separation: Quick File is optimized for
low-latency navigation; content search is optimized for retrieval, progress, grouping,
and locations. They share provider and cancellation machinery, not a
lowest-common-denominator result list.
Unlike an editor with a continuously maintained workspace index, Metabrowser must also
show whether the browser’s observed path catalog is incomplete.

## Architecture

### Search Runtime and Surfaces

`static/search_controller.js` owns provider registration, query lifecycle, cancellation,
fallback policy, result deduplication, and batch metadata.
It has no DOM dependency.
The application shell injects inventory observations and navigation actions rather than
letting search modules reach into private `app.js` globals.

UI surfaces consume the controller:

- `static/search_palette.js` is the Phase 1 transient, keyboard-first Quick File dialog
- a future navigation-panel search box is a persistent surface that can show file
  groups, content excerpts, progress, scope controls, and more results
- later plugins may add entry points only through the documented SDK and provider
  registration boundary

The controller accepts synchronous and asynchronous providers through one
promise-compatible contract:

```text
SearchRequest
  query
  target: file | content
  match: fuzzy | literal | regex | approximate
  scope (optional)

SearchOptions
  includeFallback (optional explicit complete-coverage request)

SearchProvider
  id: stable provider identifier
  activation: immediate | fallback
  supports(request) -> bool
  search(request, context, signal) -> SearchBatch or Promise<SearchBatch>

SearchBatch
  provider_id
  results[]
  complete
  truncated
  revision (optional)
  status_message (optional)

FileResult
  kind: file
  id
  path
  label
  description
  score
  match_ranges[]

TextResult
  kind: text
  id
  path
  line
  column
  excerpt
  match_ranges[]
```

`complete` describes the provider’s candidate universe, while `truncated` describes the
returned result list.
The controller never infers one from the other.
It cancels the previous request when the query, mode, or scope changes and drops any
late batch whose request identity is no longer active.
Activation defaults to `immediate`, and immediate providers run together.
Fallback providers run only when the immediate composition is empty and incomplete, or
when a surface explicitly requests complete coverage.
For file results it merges batches by path, keeps the highest-scored duplicate, and uses
provider priority plus stable path order for deterministic ties.
Each surface preserves its selected result by identity when asynchronous results arrive
so the highlight does not jump.

Phase 1 has one filename provider, so its ordinal scores are meaningful within one
batch. Before local and server filename batches can appear together, Phase 2 must either
define one cross-runtime comparable rank or let an authoritative complete batch replace
incomplete local results.
It must likewise define when complete server coverage supersedes incomplete local
coverage in aggregate status; provider-local ordinals and a conjunction of batch
completeness are not sufficient for an explicit complete search.

The first entry point always sends `{target: file, match: fuzzy}`. The contract reserves
literal and regex content search and an evidence-gated approximate-content provider
without implying that the filename fuzzy scorer can search file contents.
A future navigation-panel surface can select these capabilities explicitly and group
`TextResult` values by path without changing the Phase 1 palette.
An empty Phase 1 query shows an instruction and the observed file count rather than an
arbitrary result ordering.

The initial implementation should keep the request and result unions no larger than the
Phase 1 code needs, but its module boundary and tests must not bind providers to dialog
elements.

### Known File Catalog

`static/known_file_catalog.js` owns the minimal client-side search candidates.
It stores only the fields required for discovery and navigation: path, basename, logical
extension when available, and the source that last observed the entry.
It does not duplicate file contents, directory aggregates, plugin views, or every
`FsEntry` field.

The application shell feeds the catalog through explicit adapters:

- the initial `/api/tree` response
- every lazy `/api/tree` subtree response, including rows beyond the first mounted page
- every `/api/recent` flat response
- `fs.snapshot` and `fs.change` file entries
- successful direct navigation to a file that was not observed through another source

Observation is idempotent by path.
Directory nodes are traversed to discover file leaves but are not candidates.
A root swap or `fs.resync_required` clears the catalog before new observations arrive.
Scoped remove operations delete matching candidates, but the catalog remains explicitly
partial and potentially stale for deep paths because the depth-two stream cannot report
every deep removal.

The catalog exposes an immutable snapshot and metadata:

```text
{ files, observed_count, complete, source_summary, revision }
```

Phase 1 always reports `complete=false` because observing all visible responses does not
prove that every inventory path reached the browser.
A later provider may report complete server results without changing this local fact.

### Client Fuzzy Matching

`static/file_fuzzy_match.js` is a pure strict module with deterministic tests and no new
dependency. A candidate is eligible when every query character can be matched in order
against its basename or served-root-relative path.
Queries without `/` compare the basename first and may fall back to the full path;
queries containing `/` compare path segments directly.

The scorer returns a named ranking vector instead of hiding behavior in one unexplained
number:

```text
FuzzyRank
  match_class
  boundary_hits
  contiguous_chars
  run_count
  gap_chars
  start_offset
  candidate_length
  directory_depth
  normalized_path
  original_path
```

Results use a deterministic comparison chain in this order:

1. `match_class`: exact basename, basename prefix, contiguous basename, basename
   subsequence, path-segment match, then full-path subsequence
2. More query characters on camel-case, dash, underscore, dot, or path-segment
   boundaries
3. More contiguous matched characters
4. Fewer matched runs and fewer skipped characters between runs
5. Earlier first match and fewer unmatched candidate characters
6. Shallower directory depth
7. Normalized path using deterministic code-unit ordering, then original path, as the
   total-order tie-breaker

This ordering makes exact and basename-local matches categorically better than matches
found only in a parent directory.
It also keeps tuning reviewable: changing the priority of a named component is distinct
from changing how that component is calculated.
The implementation may encode the vector as numbers for efficiency, but must expose the
named components to tests and diagnostic fixtures.

The initial ranking policy includes:

- exact basename and basename-prefix priority
- path-segment, word-boundary, camel-case, dash, underscore, and dot boundaries
- contiguous-character preference
- gap, candidate-length, and directory-depth penalties
- case-insensitive matching with an original-path final tie-breaker

Queries containing `/` remain path-aware.
For example, `srcapp` can match `src/metabrowser/static/app.js`, while `app` gives more
weight to the basename than to a parent directory named `app`. The result includes
character ranges so the palette can highlight why a candidate matched.

`tests/fixtures/file_fuzzy_ranking.json` is the review surface for ranking behavior.
Each scenario records a query, candidate paths, expected order, a short rationale, and
tags such as `exact`, `basename-vs-parent`, `boundary`, `gaps`, `path`, `case`,
`punctuation`, `unicode`, or `tie`. The fixture must cover both obvious winners and
close calls where a maintainer may want to revise the policy.
Every ranking change updates the fixture and the spike report at
`docs/project/research/research-2026-07-31-fuzzy-file-ranking.md` with the affected
before-and-after examples.

The provider evaluates every locally known file but retains only a bounded top result
set. Small catalogs use a synchronous fast path.
Larger catalogs evaluate in cancellable chunks and yield between chunks so one query
cannot monopolize the browser event loop.
Measurements, rather than candidate count alone, decide whether a Web Worker is needed.

### Provider Selection and Fallback

Provider orchestration follows these rules:

1. The local file provider runs immediately for every non-empty filename query.
2. Phase 1 stops there and labels zero results as “No known file matches,” including the
   observed candidate count and incomplete-catalog state.
3. After the server filename provider exists, the controller starts it automatically
   only when the local result set is empty and the local catalog is incomplete.
4. An explicit “Search all indexed files” action can start the server provider even when
   local matches exist.
5. Filename results never trigger full-text work automatically.
   If filename providers return no result, the active surface may offer “Search contents
   for …” as an explicit mode change.

This policy makes the common local hit immediate, gives incomplete local search a
complete fallback, and avoids changing query meaning or starting expensive content work
without user intent.
It is also compatible with a persistent nav search box: that surface can expose file and
content modes continuously, while the palette stays specialized for navigation.

### Keyboard and Accessibility Contract

- `/` opens the finder with an empty query and prevents the browser’s quick-find action
- the global handler ignores events already prevented, modifier chords, composition, and
  editable targets; pressing `/` inside the finder inserts the character normally
- `ArrowDown`, `ArrowUp`, `Home`, and `End` change the active result
- `Enter` opens the active result
- `Escape` closes the finder and restores the element focused before it opened
- opening an already-open finder focuses and selects its query rather than creating a
  second instance
- the palette uses a labelled dialog, a combobox with `aria-expanded` and
  `aria-controls`, a listbox, options, `aria-activedescendant`, and a polite status
  region for provider progress and completeness
- mouse selection and outside-click dismissal match the keyboard result path

The palette is attached outside replaceable tree and preview containers.
Inventory renders therefore cannot discard its focus or state.
Result rows show the basename as the label and the parent path as secondary text, reuse
the existing file icon vocabulary, and mount only the bounded result set.

### Navigation and Failure Contract

Opening a file delegates to an injected application action backed by `navigateToPath`.
The action should return a success or failure result so the palette can distinguish a
successful open from a stale catalog hit.
On success, the palette closes and the action returns the preview or other destination
that should receive focus.
Cancellation, Escape, and outside-click dismissal instead restore the element focused
before the palette opened.
On a not-found response, the catalog removes that path, the palette stays open, and an
inline status says that the file is no longer available.
Other failures preserve the query and result list and expose a retryable error.

### Catalog Feed: Client-Complete Filenames

Phase 2 makes the local catalog complete instead of adding a per-query server provider.
This supersedes this document’s original constraint that the browser must not download a
complete filename catalog — that constraint was sized against unfiltered inventories,
and measurement showed ~98% of a typical inventory is gitignored (this repository: ~270
non-gitignored files out of ~12,500 indexed).
The decision record is bead `mb-ci04`; at the 100k-non-ignored design center the full
catalog is 6–8 MB of minimal JSON, 1–2 MB gzipped, transferred once.

The feed has two halves, split along what each transport is actually good at:

**Bulk: `GET /api/catalog`.** A one-shot JSON response containing every non-gitignored
file at `all-known` scope in a minimal shape —
`{complete, truncated, revision, files: [{p, e}]}` where `p` is the served-root-relative
path and `e` the logical extension.
One-shot JSON is the right transport for bulk state because the gzip middleware
compresses it automatically (SSE is never compressed — Starlette excludes
`text/event-stream`), it can carry an ETag for cheap revalidation, and it can be encoded
off the event loop instead of as one synchronous dump inside the stream handler.
The full `FsEntry` wire shape is ~308 bytes across 16 fields, most of them
tree-decoration data the catalog never reads; the minimal shape is ~60–80 bytes raw.

**Deltas: `catalog.change` on the existing event stream.** Every `fs.change` batch
already flows through one inventory choke point; that point also derives a minimal
`catalog.change` event — file upserts as `{p, e}` (an upsert whose entry is gitignored
becomes a catalog *remove*, handling ignore-state flips), removes passed through, and
directory-only batches emitting nothing.
Event-scope filtering passes non-`fs.change` event types through unchanged on every
scope, so the depth-two tree stream carries complete catalog deltas with no filter
changes, no second `EventSource`, and no separate resync story.

**Convergence without a consistency token.** The client opens the event stream first,
buffers `catalog.change` events, fetches `/api/catalog`, applies the bulk, then replays
the buffer. Ops are idempotent by path, so overlap between the snapshot and buffered
deltas converges. The catalog refetches only when delta continuity is lost: the sentinel
`fs.snapshot` that follows an event-stream reconnect, and `fs.resync_required`. Walker
completion needs no refetch — at `all-known`, live ops converge the data — but it does
flip the completeness flag, so the walker emits the already-defined `capability.update`
event when the walk finishes.

The client keeps its observation seams (initial tree, lazy subtrees, recent,
navigation): they provide coverage before the first fetch resolves and when
`EventSource` is unavailable, where the one-shot fetch alone still delivers
complete-as-of-fetch coverage.

**Bounded server search stays the beyond-cap fallback.** The original
`/api/search/files` design (consistent snapshot, Python scorer sharing the golden
fixtures, honest truncation metadata) is retained in bead `mb-3arq`, deferred until a
root whose *non-ignored* file count makes client-complete unreasonable is a demonstrated
use case. The provider runtime already supports it through fallback activation.

### Full-Text Provider

Phase 3 adds an explicit `text` mode and a separate endpoint:

```text
GET /api/search/text?q=needle&path=optional/subtree&limit=100
```

Full-text search has a different result and cost model from filename search.
Results include a file path, line and column, a bounded excerpt, and highlighted ranges.
The request contract must bound query length, subtree scope, files examined, bytes read,
wall time, result count, excerpt size, and decompression.
It applies the served-root containment and ignore policy and reads only file types the
existing preview pipeline classifies as text-searchable.

The implementation phase starts with a measured engine spike.
Metabrowser cannot assume `rg` is installed, and adding a runtime search dependency
requires supply-chain review.
The spike compares a bounded internal scanner with an optional subprocess adapter and
records cancellation, encoding, compressed-file, remote-root, and large-file behavior
before the engine becomes a contract.

Opening a text result requires a location-aware extension to the navigation action.
The file opens through the normal preview route, then a renderer that supports locations
reveals the match.
Renderers that do not support locations still open the file and report
that the exact line could not be focused.

### Separation From Unified Filtering

Quick file and full-text queries are transient discovery commands.
They do not persist through `mb.prefs`, change the Current or Recent chips, dim the
Files tree, or become a `FilterState` keyword dimension.

Complete filter hide mode needs a tree-shaped projection with ancestor directories and
filtered aggregates.
The unified-filtering plan owns that contract through a distinct `/api/filter/tree`
route. This keeps filename results flat, content results location-oriented, and filter
results hierarchical.

## Implementation Plan

### Phase 0: Existing Prerequisites

- [x] Build the bounded asynchronous inventory, lazy tree, index status endpoints, and
  live event plane
- [x] Provide `navigateToPath` and lazy reveal behavior that can open an unmounted path
- [ ] Add a monotonic public inventory revision and a revision-only event that survives
  event-scope filtering without sending deep entry snapshots

### Phase 1: Client-Only Quick File Finder

- [x] Write the fuzzy-ranking spike report and scenario fixture, including the named
  comparison vector, expected ordering, rationale, and a tuning-change checklist
- [x] Add the DOM-independent search controller, request identity, cancellation, batch
  metadata, immediate and fallback provider activation, and flat file-result composition
- [x] Add the strict `known_file_catalog.js` module and feed it from initial tree, lazy
  tree, Recent, event, and successful-navigation observations
- [x] Add the pure fuzzy matcher with the documented comparison vector, path-aware
  scoring, match ranges, stable ties, and shared golden fixtures
- [x] Add a local provider that searches all catalog candidates, retains a bounded top
  set, yields during large scans, and cancels obsolete queries
- [x] Add `search_palette.js`, the `/` shortcut, accessible dialog and listbox behavior,
  focus restoration, pointer interaction, and a visible candidate-completeness status
- [x] Keep palette rendering and selection state outside provider implementations; add a
  headless contract test proving the local provider can run without palette DOM
- [x] Inject the existing navigation action, return an open outcome, and handle stale
  not-found candidates without losing the active query
- [x] Add performance fixtures for result latency, input responsiveness, and DOM count
  across shallow, Recent-sized, and heavily expanded client catalogs

### Phase 2: Client-Complete Catalog Feed

- [x] Add the `catalog.change` derivation at the inventory emit choke point, with
  ignore-flip removes and directory skipping
- [x] Emit `capability.update` on walker completion so completeness is push-based
- [x] Add `GET /api/catalog` with the minimal non-gitignored file shape, off-event-loop
  encoding, an ETag with 304 support, and honest complete/truncated metadata
- [x] Give the known-file catalog a bulk-apply path, a `catalog.change` apply path, a
  real completeness state, and a revision-memoized snapshot
- [x] Add the catalog feed module owning connect-then-fetch ordering, delta buffering
  and replay, and sentinel/resync refetch triggers
- [x] Wire the feed into the event-stream handlers and update palette and provider
  status wording for the complete case
- [ ] Measure payload size, transfer time, and scan latency at the inventory cap

The feed is authoritative about membership, not just contents.
A payload from a finished walk lists every file the index holds, so applying it retires
feed-sourced paths it no longer names; that is what lets a refetch express a deletion
that happened while the stream was down.
Paths seated by explicit navigation are the one exception, because a gitignored file the
user opened is absent from the feed by design.

Known limits:

- A truncated walk is complete for the index and permanently incomplete for the root, so
  the catalog reports incomplete coverage and the beyond-cap fallback stays deferred to
  `mb-3arq`.
- An open search does not re-run when coverage grows underneath it (`mb-lzvb`), and
  catalog removals still scan every entry (`mb-r8yg`).

### Phase 2 (deferred): Bounded Server Filename Search

Deferred to bead `mb-3arq` as the beyond-cap fallback; see “Catalog Feed” above for the
retained scope.

### Phase 3: Bounded Full-Text Search

- [ ] Run and record the engine spike before selecting an internal scanner, optional
  subprocess adapter, or other implementation
- [ ] Define text-searchability, encoding, compressed-file, large-file, ignore, timeout,
  byte, result, and excerpt policies
- [ ] Add bounded `/api/search/text` execution, cancellation, progress, and truncation
  metadata
- [ ] Add the explicit text mode, the no-filename-match content-search action, a
  persistent nav-panel search surface, grouped path/location results, and location-aware
  navigation
- [ ] Start with literal content matching; expose regex or approximate matching only
  through provider capability metadata and after separate correctness and performance
  evidence
- [ ] Test supported and unsupported renderers, stale files, concurrent changes, remote
  roots, and partial results

### Phase 4: Evidence-Gated Indexing

- [ ] Evaluate a secondary in-memory filename index only if bounded inventory scans miss
  the server query-latency budget
- [ ] Evaluate persisted filename or full-text metadata only if measured warm-start or
  capacity costs justify invalidation, versioning, and supply-chain complexity
- [ ] Evaluate a Web Worker only if chunked local search misses the input-responsiveness
  budget

## Testing Strategy

- Unit-test catalog ingestion, deduplication, source metadata, scoped removal, root
  resync, and immutable snapshots
- Golden-test fuzzy scoring for basename preference, boundaries, gaps, path queries,
  case, punctuation, Unicode, equal scores, and no match in JavaScript and Python
- DOM-test shortcut guards, focus restoration, composition, combobox/listbox semantics,
  result navigation, selection stability during asynchronous updates, outside click, and
  error recovery
- Integration-test initial tree, lazy subtree, Recent, event, and direct-navigation
  candidates flowing into one catalog
- Route-test malformed and oversized queries, containment, ignore policy, aborts,
  concurrent inventory changes, stale revisions, timeouts, and independent truncation
  fields
- Real-browser-test opening `/`, fuzzy selection of an unmounted file, a zero-local
  fallback, full-text mode switching, and location reveal
- Record server work, client input delay, payload size, and mounted result count against
  public synthetic large-tree and large-text fixtures

## Risks and Mitigations

| Risk | Mitigation |
| --- | --- |
| Users mistake local results for the full root | Always show observed count and incomplete state; phrase zero results as “No known file matches” |
| A deep known file is renamed or removed outside the event scope | Treat navigation as authoritative, remove stale not-found hits, and add revision-backed server search in Phase 2 |
| Fuzzy scoring blocks typing as the observed catalog grows | Bound displayed results, cancel obsolete searches, scan in yielding chunks, and add a Worker only after measurement |
| Server results reorder the highlighted local row | Preserve selection by result identity and use deterministic provider priority and tie-breaking |
| Automatic full-text fallback surprises users or scans large roots | Offer an explicit content-search action rather than starting content work automatically |
| One endpoint accumulates incompatible result shapes | Keep `/api/search/files`, `/api/search/text`, and `/api/filter/tree` separate behind one UI provider contract |
| `/` interferes with document editing or browser behavior | Ignore editable, composing, modified, and already-handled events; cover every guard in DOM and real-browser tests |

## Rollout Plan

Phase 1 is a client-only enhancement over paths the browser has already received.
It adds no server route, startup fetch, dependency, or complete-inventory transfer.
It adds no public SDK method, persisted preference, or wire-format compatibility
requirement. Phase 2 makes filename coverage complete when necessary.
Phase 3 adds content search as an explicit mode after its engine and resource budgets
are measured.

## Phase 1 Spike Findings

Phase 1 is ready for interactive testing as a client-only navigation spike:

- `/` opens one modal Quick File surface; filename and path input uses the documented
  ordered-subsequence rank vector and opens through normal preview navigation
- the catalog includes files learned from initial and lazy trees, Recent responses,
  inventory events, and successful direct navigation, regardless of mounted tree rows
- search retains at most 100 results, cancels obsolete work, yields during large scans,
  and makes no search request
- the runtime keeps immediate and fallback providers separate, so a later server
  filename provider can run after an empty incomplete local result or an explicit
  complete-search action
- keyboard, pointer, focus, modal semantics, stale results, duplicate basenames, lazy
  unmounted paths, and replacement queries passed DOM and real-browser acceptance

The [ranking report](../../research/research-2026-07-31-fuzzy-file-ranking.md) records
the golden scenarios and measured shallow, 2,000-file, 50,000-file, and real-browser
fixtures. The full repository gate passed with the spike enabled.

The remaining limits are deliberate or evidence-gated:

- local coverage remains partial until Phase 2 adds complete indexed filename search
- a query uses one catalog snapshot; files observed while that query remains open appear
  after the next input change or palette reopen rather than triggering an automatic
  rerun
- the local provider publishes one completed batch, so 50,000 observed files took about
  0.8 seconds to complete on the measured machine even though chunking kept queued input
  responsive
- matching does not perform typo correction, transposition, accent folding, or Unicode
  canonical normalization
- provider scores are Phase 1 batch ordinals; Phase 2 must resolve comparable ranking
  and aggregate completeness before exposing an explicit complete filename search
- content search, grouped excerpts, location reveal, and a persistent navigation-panel
  surface remain Phase 3 work

## Open Questions

- What local-result threshold should start the server provider after the initial
  zero-result policy has real usage data?
- Which query-latency and input-delay budgets should trigger a secondary filename index
  or Web Worker?
- Which full-text engine satisfies offline installation, cancellation, remote-root,
  encoding, and supply-chain constraints?
- Which core and plugin renderers should support exact line and column reveal in the
  first full-text phase?
- Should a future persistent full-text panel share query history with the transient
  palette, or only reuse providers and result renderers?

## Phase 1 Acceptance Criteria

- `/` opens one finder and does not fire from editable, composing, modified, or
  already-handled keyboard events
- Typing fuzzy-matches every file observed from tree, lazy subtree, Recent, event, and
  successful navigation sources without making a search request
- Basename matches rank above equivalent parent-path matches and ordering is stable
- Arrow keys, Home, End, Enter, Escape, pointer selection, focus restoration, and screen
  reader semantics work as documented
- Selecting a result opens it through existing navigation even when its tree row is not
  mounted
- A stale not-found result is removed without clearing the query
- The finder reports observed candidate count and incomplete local coverage
- Search work and mounted results remain bounded and do not delay initial tree or direct
  file preview

## References

- [Core architecture](../../../architecture.md)
- [Design system](../../../design-system.md)
- [Scanning state and recent directories](plan-2026-07-16-scanning-state-and-recent-directories.md)
- [VS Code Quick Access provider](https://github.com/microsoft/vscode/blob/main/src/vs/platform/quickinput/browser/pickerQuickAccess.ts)
- [VS Code file and text search service](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/services/search/common/search.ts)
- [IntelliJ IDEA Search Everywhere](https://www.jetbrains.com/help/idea/searching-everywhere.html)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
