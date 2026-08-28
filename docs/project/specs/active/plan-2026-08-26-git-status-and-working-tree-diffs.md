# Feature: Git Status and Working-Tree Diffs

**Date:** 2026-08-26

**Author:** Joshua Levy (with LLM assistance)

**Status:** Draft

## Vision

The Git tab should explain both recorded history and the repository state that has not
become history yet.

For an ordinary local repository, Metabrowser will show unresolved conflicts, staged
changes, unstaged changes, and untracked files above the existing commit graph.
Selecting one status row opens a focused, single-file diff in the main pane through the
same File Diff Format renderer used for commits and patch files.

The feature is observational.
It reads `HEAD`, the index, and the working tree without taking optional Git locks or
changing any of them.
It does not stage, unstage, discard, edit, commit, or resolve.
That boundary lets dirty repositories become first-class browsing targets without
turning the Git panel into an editor or weakening the current read-only model.

The
[Git-status research brief](../../research/research-2026-08-26-git-status-and-dirty-working-trees.md)
records the Git and VS Code source review behind this design.

## Release Principle

This plan has two implementation phases, each intended to land as one independently
reviewable pull request:

1. a measured, typed status and one-file comparison backend; and
2. the Git-panel experience, live invalidation, and design-system integration.

The first phase is testable through stable internal APIs and File Diff Format documents
without shipping a half-working browser control.
The second phase owns every user-visible route, interaction, lifecycle, and
accessibility change.

No phase adds a speculative compatibility layer.
The Git API, built-in diff data hook, browser shell, and built-in assets ship together
and may change together as internal contracts.

## Goals

- Show Git working state in the existing Git tab without displacing history.
- Preserve Git’s index/worktree distinction, including a file that appears in both
  staged and unstaged groups.
- List conflicts, staged changes, unstaged changes, and untracked files in a stable,
  documented order.
- Render one selected status entry through File Diff Format v1 and the existing diff
  plugin.
- Support ordinary modifications, additions, deletions, renames, copies, type changes,
  intent-to-add, unborn branches, binary files, symlinks, submodules, and unresolved
  states honestly.
- Parse arbitrary path bytes without splitting or corrupting adjacent records.
- Keep status acquisition and one-file diff materialization bounded, cancellable,
  coalesced, and off the event loop.
- Prevent status and diff reads from invoking repository-configured fsmonitor, hook,
  external-diff, or text-conversion programs.
- Refresh on demand and after relevant working-tree or Git-control-file changes without
  starting an automatic request storm.
- Give a status selection a canonical, reloadable browser URL.
- Reuse the status service’s clean-tree predicate for repository-cache integrity when
  the cache phase is implemented.
- Document every new route, wire model, component, state, and design-system rule beside
  its implementation.

## Non-Goals

- Stage, unstage, discard, restore, commit, stash, checkout, merge, or rebase actions.
- Partial staging or any line-level mutation control in the diff view.
- Editing a selected file from its diff.
- A three-way base/ours/theirs merge editor or conflict-resolution workflow.
- Dirty-diff gutter marks in ordinary file previews.
- Git status decorations in the Files tree or browser tab title.
- A tree projection, grouping by directory, sorting preferences, filters, or ignored
  file display.
- Recursively listing a submodule’s dirty files as members of the parent repository.
- Opening a served subdirectory as a repository.
  The current exact repository-root gate remains.
- Hosted-provider state such as pull requests, issues, checks, or reviews.
- Making cached repository checkouts editable.
  Cache entries remain read-only and normally clean.
- Changing File Diff Format v1. The existing schema already has commit, index, worktree,
  and empty snapshots.
- A public plugin SDK for source-control panels or comparison sources.

## Background

### Current Git surface

The Git feature already has the infrastructure this work should extend:

- `metabrowser/git/process.py` is the only Git subprocess boundary.
  It uses fixed argument vectors, returns raw bytes, suppresses optional locks and
  credential prompts, scrubs repository-pinning environment variables, caps output,
  times out, and reaps on cancellation.
- `metabrowser/git/repo.py` proves that the served root is the repository’s exact
  working-tree root and supports linked worktrees through Git’s own discovery.
- `/api/git/repo`, `/api/git/refs`, `/api/git/log`, and `/api/git/commit/{revision}`
  provide a typed, read-only collection API.
- `static/git-panel.js` owns the lazy Git tab, history paging, selection, hover, and
  commit detail.
- `metabrowser/diff/adapters/git.py` turns immutable revision comparisons into File Diff
  Format.
- the built-in diff plugin validates and renders those documents, including binary,
  deferred, oversized, syntax, folding, unified, and split states.
- the browser URL grammar addresses commit comparisons as `/commit/<revision>[/<file>]`.

Status is therefore a new Git acquisition and comparison source.
It is not a new renderer, provider model, or repository-discovery path.

### Why status cannot be one dirty flag

Git has three content layers: `HEAD`, the index, and the working tree.
A path may have a staged change from `HEAD` to the index and another unstaged change
from the index to the working tree.
A boolean `dirty`, or one normalized kind per path, cannot tell the user what is ready
for the next commit.

The domain model must preserve `X` and `Y` from Git status and then project comparison
rows. A record such as `MM` produces two rows:

- Staged Changes: `HEAD → index`; and
- Changes: `index → worktree`.

The UI is allowed to repeat the path because the comparisons are different.
Deduping it would be a correctness bug.

### Relationship to repository caching

The [repository-library plan](plan-2026-08-11-open-repo-from-git-url.md) publishes a
pinned, read-only `gitroot`. Browsing and ref refresh should leave its working tree
clean. The status feature remains independent:

- an ordinary local repository may be dirty and shows its entries;
- a healthy cached repository reports clean and shows the compact clean state;
- a dirty cached repository is a cache-integrity failure, not permission to browse and
  normalize the mutation silently; and
- cache integrity calls the status service’s `is_clean` predicate so the definition of
  clean cannot drift between two parsers.

That last point is a real ordering constraint, not just a shared helper.
`is_clean` ships in Git-status Phase 1 (`mb-u4mf`), so repository-library Phase 1B
depends on it and is tracked that way in both the
[repository-library plan](plan-2026-08-11-open-repo-from-git-url.md) and the bead graph.
Landing Phase 1B first would leave cache integrity either unchecked or served by the
second porcelain parser both plans exist to prevent.

The predicate is also gated: below Git 2.36 the status service returns
`unsupported_git_version` and there is no predicate to call.
Cache integrity then reports its check as **unavailable**. It must not infer clean from
the absence of a result — an unverified entry and a verified-clean entry are different
states, and only one of them justifies serving the cached root without a warning.

The status API contains no cache-entry ID, source URL, GitHub identity, or provider
metadata.

## Design

### User model and panel structure

Once repository discovery succeeds, the Git panel has two top-level sections:

1. **Changes**; and
2. **History**.

Status and the first history page load concurrently the first time the Git tab is shown.
A failure in one section does not erase the other.

There is a third request to place in that order.
`/api/git/summary` backs the history tally and runs one graph traversal, so the panel
defers it until after the first history page paints rather than racing it.
Status must not undo that deferral: the ordering is status and the first history page
together, then the summary once the first page is on screen.
That ordering is fixed here rather than left to implementation: status is not permitted
to move the summary earlier to simplify its own loading sequence.

Changes has four possible states:

- **Loading:** the ordinary panel skeleton and busy semantics;
- **Clean:** a compact factual `Clean` value in the Changes header and no fake row;
- **Dirty:** nonempty groups and their rows; or
- **Degraded:** a typed timeout, failure, or partial-result notice plus manual refresh.

Dirty Changes starts expanded.
History remains expanded.
Within Changes, nonempty groups appear in this order:

1. Conflicts;
2. Staged Changes;
3. Changes; and
4. Untracked.

Each group header shows its row count and uses the section-disclosure contract.

The panel already has a header row.
`.git-history-summary` carries the history tally directly above the graph, and it
belongs to History rather than to the panel as a whole.
Changes and History therefore each own their own header, stacked in that order, rather
than sharing one region:

```text
Changes  ▾   3 changes           ← Changes disclosure header
  …rows…
History  ▾                       ← History disclosure header
  begun 3mo ago · 1,204 commits   ← the existing tally, unchanged
  …graph…
```

Two headers is the honest structure because the counts answer different questions and go
stale independently: the tally changes when history moves, the Changes count when the
working tree does. Merging them would also put a status count above the scroll origin
that [Changes above a virtualized History](#changes-above-a-virtualized-history)
requires History to keep, which is the coupling this plan exists to avoid.
The tally keeps its current markup, class names, and lazy load; Changes adds its own
header beside it and does not restyle it.
Group counts count comparison rows.
The top-level summary carries both comparison-entry and unique-path totals so a
partially staged file does not make an accessible label claim there are two files.

The initial projection is flat.
A row shows:

- a non-color-only status badge;
- the basename in ordinary path typography;
- its parent directory in muted text;
- `old → new` for rename and copy identity;
- inline addition/deletion counts when already available without another unbounded
  command; and
- an explicit submodule or conflict label when a letter alone is insufficient.

The status letters are:

| Meaning | Badge |
| --- | --- |
| Added | `A` |
| Modified | `M` |
| Deleted | `D` |
| Renamed | `R` |
| Copied | `C` — parser only; unreachable under the baseline rename policy |
| Type changed | `T` |
| Untracked | `?` |
| Unmerged | `U` |

Badge text, group, tooltip, and accessible name carry meaning.
Color is secondary.

### Changes above a virtualized History

Continuous virtualized history changed what “put a section above History” costs, and
this plan predates it.
The constraint is concrete.

`git-history-window.js` is a pure computation module: `read(scrollTop, viewportHeight)`
maps a scroll position to a logical row range, and `rebaseToOrdinal` returns a new
`scrollTop` when the physical segment must move before the 8,000,000-pixel budget.
Its caller in `git-panel.js` passes the scroller’s raw `scrollTop` and writes the
rebased value straight back.
The window therefore assumes **history row 0 sits at scroll offset 0 of the scroller it
is given**.

A Changes section in that same scroller breaks the assumption in both directions.
Reads map to the wrong logical row by the height of the Changes block, and a rebase
write-back jumps the viewport by that same amount.
The offset is not a constant that could simply be subtracted: Changes is absent when the
tree is clean, grows with the number of entries, and expands and collapses under a
disclosure — so it changes while the user scrolls.

This is not hypothetical, and the evidence arrived before this plan was implemented.
The Git header tally added `.git-history-summary` above `.git-graph-list` in the same
scroller, in normal flow, which already breaks the assumption by roughly one row.
The 64-row overscan absorbs it, so nothing looks wrong while scrolling, and the
`scrollTop` write-backs land about a row off target.
It is tracked as `mb-180g`.

The lesson for this plan is the important part: the first element ever added above the
virtualized list silently violated the contract, and it was small and fixed-height.
Changes is large, variable, and user-toggled.
Whatever fix `mb-180g` takes — a separate scroll container, or an explicit conversion at
the boundary — must land before Changes is built on top of it, or this plan inherits a
defect and multiplies it.

Changes therefore **must not share a scroll origin with History.** Two acceptable
structures:

1. **Separate scrollers.** Changes and History are peer disclosures, each owning its own
   scroll container. The window keeps its origin invariant untouched, and each section
   scrolls independently.
   This is the baseline.
2. **Non-scrolling Changes.** Changes occupies a bounded, non-scrolling region above a
   History that still owns the full scroller.
   Simpler, but it caps how many status rows are reachable without its own overflow
   treatment.

What is **not** acceptable is one scroller with an offset correction applied at the call
site. That reintroduces the coupling the virtual window was written to avoid, has to be
re-derived on every expand, collapse, and status refresh, and silently corrupts the
segment-rebase budget, which assumes the segment owns the whole scroll range.

Phase 2 states which structure it chose and adds a browser test that scrolls deep into
history with Changes both expanded and collapsed, asserting the resolved logical row is
unaffected by the Changes block’s height.

### Selection and canonical route

Selecting a status row replaces the main content with that row’s one-file diff and
selects the Git tab.
The canonical browser address is:

```text
/status/<scope>/<entry-id>
```

`scope` is one of `conflict`, `staged`, `unstaged`, or `untracked`. `entry-id` is a full
deterministic digest over scope and raw path identity.
The digest keeps the route exact for paths that are not valid UTF-8, for names that
contain characters excluded by the ordinary file URL grammar, and for staged and
unstaged rows at the same path.
The readable path stays in the selected row and main view rather than becoming a second,
lossy route identity.

`MetabrowserRoutes.statusHref` and `parseStatus` are the only codec.
They validate the scope and full digest and reject extra or malformed segments.

This is a deliberate departure from the URL grammar and must be registered as one.
[`docs/architecture.md`](../../../architecture.md) states the grammar as an address
space plus a path within it, which is why `/view/<path>` and `/commit/<rev>/<file>` read
as “the same grammar over two address spaces”.
`/status/<scope>/<entry-id>` substitutes an opaque digest for that trailing path,
because a status row has no addressable path in the grammar’s sense: two rows can share
one display path, and a path need not be valid UTF-8. A path-shaped alternative would
need a second codec for the cases the first cannot express, which is worse than one
exact codec.

When Phase 2 registers the route, add that reasoning to the grammar table rather than
letting a reader discover an apparent inconsistency and assume it was an oversight.

On reload, the Git panel fetches current status and resolves `entry-id`. If the entry no
longer exists, the panel keeps the current status list, presents a concise stale
selection notice, and does not substitute a different row with the same display path.

Status rows are a navigational row collection.
Exactly one row is in the Tab order; Arrow Up and Arrow Down move and open; Enter,
Space, and pointer activation open; and selection mutates only the previous and next
row. Navigation claims the route and paints pending state before awaiting diff assets or
data, then swaps atomically through the existing preview readiness lifecycle.

### Acquisition command

`GitStatusService` acquires one repository snapshot with a command equivalent to:

```shell
git <common-hardening-args> \
  -c core.fsmonitor=false \
  -c core.hooksPath=<package-owned-no-hooks-directory> \
  status \
  --porcelain=v2 \
  -z \
  --branch \
  --untracked-files=all \
  --find-renames=<measured-threshold> \
  --ignored=no \
  <explicit-submodule-policy>
```

The actual argument vector is fixed in Python and contains no shell.
`<common-hardening-args>` is `metabrowser.git.process.GIT_COMMON_ARGS`, which already
supplies `--no-optional-locks` and `core.quotepath=false`; status does not restate them,
because a second copy of a centrally owned flag is a second thing to keep correct.
(`core.quotepath` is additionally inert under `-z`, which emits raw path bytes without
quoting.) The current Git environment hardening remains authoritative.
The submodule option is finalized by the Phase 1 measurement gate; it must be explicit
and recorded beside the result rather than inherited from user config.

### Rename and copy policy

The baseline policy is **renames only**, and that is a deliberate limit rather than an
omission:

- `git status` has no `--find-copies` option.
  Copy detection is reachable only through `status.renames=copies`.
- `--find-renames=<n>` on the command line overrides `status.renames` entirely.
  Passing it is what keeps a user’s `status.renames=false` or `status.renames=copies`
  from reaching a machine-facing command, which is the behavior this plan wants — but it
  also means the two settings cannot be combined.

So under the baseline argv a `2 C...` record cannot occur, and a copied file is reported
as an addition. That is what Git does by default and what VS Code shows.

The consequence to accept knowingly: the immutable diff adapter runs `-M -C`, so the
same file can render as `copied` under `/commit/<rev>` and as `added` under `/status/`.
The alternative costs more than it returns right now — enabling
`-c status.renames=copies` forfeits explicit similarity control, since the threshold can
then only come from Git’s default, and copy detection scans candidate sources on every
acquisition.

Phase 1 therefore measures copy-detection cost as a third evidence gate (see
[Open Decisions](#open-decisions)) and records the decision beside the measurement.
Until that gate says otherwise, `C` is parser-level coverage only: the porcelain parser
must accept and normalize `2 C...` records so a future policy change is a one-line argv
edit, but no badge, comparison mapping, or design-system row may present copies as a
state the shipped policy can produce.

The status capability requires Git 2.36 or newer.
The floor is not for porcelain v2; that format is older.
It ensures `core.fsmonitor=false` is interpreted as a boolean rather than as a hook
pathname. Repository discovery and history continue to use their existing behavior below
the floor, while status returns a stable `unsupported_git_version` state.
There is no porcelain-v1 or hook-enabled compatibility path.

`--branch` lets `HEAD` identity and status entries come from the same command.
The service cross-checks that identity with `RepoContext`; disagreement during a
checkout is a stale acquisition to retry once, not a mixed snapshot to publish.

Ignored files are never requested.
Individual untracked files are required because a directory placeholder cannot open a
one-file diff.

### Porcelain-v2 parser

The parser consumes raw bytes incrementally and recognizes these record families:

- `1`: ordinary tracked entry;
- `2`: rename or copy plus a second NUL-delimited original path;
- `u`: unmerged entry with stages 1, 2, and 3;
- `?`: untracked path;
- `!`: ignored path, rejected from the configured command but parsed defensively; and
- `#`: optional headers, including branch identity.

Unknown optional headers are ignored as Git requires.
An unknown record family, invalid field count, malformed mode, malformed object ID,
incomplete rename record, or trailing partial record is a typed acquisition failure.
The parser never skips ahead to a later NUL after structural corruption because that
could attach status metadata to the wrong path.

Paths use one shared Git path codec extracted from the immutable diff adapter:

- valid UTF-8 is carried as `path`;
- invalid UTF-8 also carries `path_b64` and a replacement-character display string;
- deterministic comparisons, sort order, and row identity operate on raw bytes; and
- HTML and URL output always escape the display string.

Tracked entries are sorted after parsing because Git documents their order as undefined.
Sorting uses scope order, current raw path, original raw path, and record kind.
No API, test, or generation hash depends on producer order.

### Domain and wire models

The status service owns a lossless raw record model and a normalized response model.
The browser consumes the normalized model only.

`GitStatusSnapshot` contains:

- `is_repo` and current `head`;
- an opaque normalized `generation`;
- `groups` in canonical order;
- exact returned-entry and unique-path totals;
- `truncated` plus a stable truncation reason when applicable;
- the explicit rename and submodule policies used; and
- no absolute path, command stderr, timestamp, or presentation label.

`GitStatusGroup` contains a comparison `scope` and ordered `entries`.

`GitStatusEntry` contains:

- `id`, a SHA-256 digest over scope, current raw path, and original raw path;
- `scope`;
- normalized `kind`;
- `index_status` and `worktree_status`;
- current and original path display/base64 pairs;
- `entry_type`;
- modes for available layers;
- object IDs for available `HEAD`, index, and conflict stages;
- rename/copy similarity;
- normalized conflict kind;
- submodule commit, modified-content, and untracked-content flags;
- `availability`; and
- no browser label, CSS class, icon name, or diff markup.

The same raw porcelain record may produce two `GitStatusEntry` values with distinct
scopes and IDs. Conflicts produce one conflict entry and are not also projected through
ordinary `X` and `Y` rules.

“Available” above is a real distinction with a specific encoding, because porcelain v2
does not omit an absent layer — it emits a placeholder.
An intent-to-add entry is:

```text
1 .A N... 000000 000000 100644 000…0 000…0 newfile.txt
```

The all-zero object ID and mode `000000` mean *this layer has no object*, not *this
object is all zeros*. Normalization maps both to an absent mode and an absent object ID,
which is what lets the staged side resolve to an `empty` File Diff Format snapshot
rather than a bogus one.
A validator that checks object IDs for 40 lowercase hex characters without this rule
will either reject a legitimate record or promote a null OID into a `git cat-file`
argument, so the rule belongs in the validator and in the parser tests, with
intent-to-add as the named case.

`git/wire.py` adds TypedDict definitions and runtime validators.
Required-key gate sets, enum checks, object-ID validation, group-order validation,
unique-ID validation, raw path/base64 consistency, and count reconciliation follow the
existing Git wire model.

### Status generation and consistency

The list generation is a SHA-256 digest over canonical serialized status facts:

- current `HEAD` state;
- normalized, sorted raw records;
- resolved per-worktree index identity; and
- the acquisition policies that affect the result.

It is an opaque change token, not a content snapshot ID. A file can change from one
modified byte sequence to another while remaining `M`.

The status response uses `Cache-Control: no-store` and its generation as an `ETag` for
conditional refresh.
The service coalesces concurrent acquisitions per served root and never publishes a
partially parsed record.

A one-file comparison request includes `entry-id` and the generation the browser saw.
The handler reacquires or validates current status before materializing.
A mismatched generation or missing entry returns `409` with a stable `stale_status` code
and the latest generation, never an arbitrary current-path comparison under the old
route.

The working-tree adapter samples relevant mutable identities before and after
materialization:

- `HEAD`;
- the resolved index file’s device, inode, size, and nanosecond modification time; and
- `lstat` identity for the selected worktree path when it exists.

It retries once if these change.
A second change returns File Diff Format availability `stale` or the route’s typed stale
response. It never caches a successful worktree document under a commit-style immutable
key.

### Comparison mapping

A new `GitWorkingTreeDiffSource` lives beside, not inside, `GitDiffSource`. The
immutable adapter continues accepting revision intents only.
The new source accepts a validated `GitStatusEntry` from the status service; callers
cannot pass arbitrary revisions or pathspecs.

The mappings are:

| Scope | Left | Right | Git/file acquisition |
| --- | --- | --- | --- |
| Staged | `HEAD` or empty | index | Path-limited diff for ordinary entries; bounded complete-scope selection for renames |
| Unstaged | index | worktree | Path-limited diff for ordinary entries; bounded complete-scope selection for renames |
| Untracked | empty | worktree | bounded safe-path read and an all-addition hunk |
| Conflict | stage 1 or empty | worktree result | bounded Git-object plus safe-path reads, with an unmerged warning |

For staged comparisons, omitting an explicit base from `git diff --cached` is
intentional: Git compares with `HEAD` and treats an unborn branch as an empty base.
The resolved File Diff Format document still records the actual empty or commit
snapshot.

For rename and copy entries, the validated entry supplies both paths.
A path-limited Git diff can split a rename into delete plus add, so the baseline uses a
bounded complete scope diff and selects the matching patch section by raw side identity,
reusing the immutable adapter’s parsed-side matching behavior.
If that bounded command cannot materialize the section, the entry reports `too_large`;
it does not silently substitute an inferior full-file delete/add display.
Phase 1 measures this path separately so a later object-to-object optimization is
evidence-driven.

Every Git patch command disables external diff and text-conversion helpers.
Status viewing must not execute repository-configured programs.
All commands continue through the bounded Git runner.

### File Diff Format projection

Every successful selection returns an ordinary File Diff Format v1 document with one
manifest entry:

- `resolved.source.name` is `git_worktree`;
- `left` and `right` use `commit`, `index`, `worktree`, or `empty` as appropriate;
- mutable snapshots carry generation values;
- `comparison_id` is derived from entry ID and the materialized side generations;
- options state the diff algorithm and rename policy actually used;
- warnings state live or unmerged limitations;
- totals cover the one entry only; and
- availability uses the existing `ready`, `binary`, `too_large`, `timed_out`, `stale`,
  `failed`, or `unsupported` vocabulary.

No status-only field is added to the File Diff Format schema.
Scope, raw `XY`, conflict kind, and submodule dirt belong to the status response and the
surrounding Git view, not a source-neutral change-set document.

The built-in diff plugin adds a data hook:

```text
GET /api/plugin/diff/working-tree?entry=<entry-id>&generation=<generation>
```

It returns a File Diff Format document or the standard plugin error envelope.
The route accepts no raw path.
The existing `comparison` hook remains revision-only.

### Special cases

| Case | Required behavior |
| --- | --- |
| Clean tree | Changes header says `Clean`; no empty fake group or row |
| Partially staged file | Appears once in Staged Changes and once in Changes, with different diffs |
| Unborn branch | Staged comparison uses empty → index; history remains empty |
| Intent to add | Appears in Changes as empty/index → worktree and renders the whole file as added |
| Staged rename plus unstaged edit | Staged row preserves old → new; unstaged row resolves the index-side renamed path correctly |
| Deleted file | Missing side is empty; row remains navigable even though Files cannot open it |
| Untracked text | All lines are additions; no temporary file or `--no-index` process is required |
| Binary file | One manifest entry with binary availability and no invented line counts |
| Oversized file | One entry with `too_large`, the existing bounded notice, and no unbounded read |
| Symlink | Compare link targets without following the link outside the served root |
| Submodule | Show the gitlink and porcelain-v2 state flags; do not enumerate the nested repository |
| Conflict with working result | Show base/empty → working result with an explicit unmerged warning |
| Conflict without working result | Show the conflict identity and `unsupported` patch availability; do not invent a side |
| Non-UTF-8 path | Preserve raw base64 identity, deterministic ID, escaped display path, and exact lookup |
| Newline/tab/quote in path | NUL parser and entry-ID route remain exact |
| Linked worktree | Resolve per-worktree index and Git control files through Git, never literal `.git/index` |
| Sparse checkout | Report what Git reports; do not treat absent skip-worktree paths as deletions |
| Concurrent edit | Retry once, then return stale rather than mix sides |
| Truncated status | Render complete returned rows plus warning; never claim the repository is clean or totals are complete |

### Bounds and performance

Phase 1 begins with measurement rather than importing VS Code’s constants.
The corpus must cover:

- tracked modifications distributed across directories;
- files that are both staged and unstaged;
- flat and nested untracked populations;
- additions, deletions, renames, copies, and type changes;
- binary and large files;
- conflicted states;
- a repository with submodules;
- a large stat-dirty but content-identical population, as a working tree looks after a
  branch switch, a rebase, or a build that touches tracked files; and
- UTF-8 and raw-byte path edge cases.

The stat-dirty case is not a variant of ordinary modifications and must not be dropped
as one. `GIT_OPTIONAL_LOCKS=0` is what makes this feature observational — it is why
status never writes the user’s index, which the Phase 1 acceptance boundary requires —
but it also means the refreshed stat cache is never persisted.
Git re-hashes every stat-dirty file on every acquisition, and that cost does not
amortize the way it does for an ordinary `git status` at the terminal.

That matters here specifically because Phase 2 refreshes on filesystem-change bursts, so
the worst case is a repeating cost on exactly the workflows that generate the most
events. Pick the debounce and the status timeout from this measurement, not from the
clean-tree number.

Measurements record:

- process start to first complete record;
- total status latency;
- output bytes and record counts;
- peak Python retained bytes;
- projection and JSON serialization time;
- one-file diff latency and bytes by scope;
- browser time to first status row and painted selected diff; and
- DOM nodes and interaction cost at the candidate row cap.

The implementation then introduces named settings for status timeout, output bytes,
entry count, and optional browser row budget only where the evidence shows a bound is
needed. Each constant cites the measurement beside it.
The ordinary Git subprocess limits remain a final safety net.

Status acquisition needs a record-aware streaming runner, and half of it now exists.
`metabrowser.git.process.spawn_git_process` landed with continuous history: it returns a
live process whose streams the caller owns, with the same executable lookup, environment
isolation, fixed arguments, and spawn-failure translation as `run_git`, plus
`terminate_git_process` as its counterpart.
Status uses that seam and adds only the record-framing layer on top; it does not
introduce a third way to start a Git process.
It shares the current subprocess environment, stderr cap, timeout, cancellation, and
termination behavior, but feeds complete records to the porcelain parser and can stop at
an entry or byte budget.
A stopped producer yields a partial `GitStatusSnapshot` with `truncated: true`; it is
not translated into a generic Git failure.
Structural parse errors still fail the whole acquisition.

Only one status process may run per root.
Concurrent first-show, route-restore, manual refresh, and invalidation requests join or
supersede it. Ordinary one-file diff requests remain path-scoped.
Rename and copy requests may scan one bounded complete scope to preserve rename
semantics, return only the selected section, and report `too_large` instead of widening
a bound.

### Invalidation and refresh

Phase 2 adds a root-scoped `GitStatusCoordinator` with a disposal path.
It starts lazily after the first status request, stops on served-root replacement and
application shutdown, and watches two sources:

- existing working-tree inventory events; and
- targeted Git-control paths resolved for the current worktree, including the index,
  `HEAD`, refs or packed refs, and merge/rebase/cherry-pick markers needed to detect
  group changes.

The coordinator emits one `git.status-change` invalidation event after a measured
debounce. It does not run `git status` per filesystem event.
The browser behavior is:

- if Git is visible, coalesce and refresh after the debounce;
- if Git is hidden, mark it stale and refresh on the next show;
- if a status diff is selected, mark it stale immediately and reload it only after the
  refreshed list proves the same entry still exists;
- if `HEAD` changed, also reset the existing history state through its current refresh
  path. Since continuous history landed, that path is session-based: a moved `HEAD`
  changes the scope fingerprint, so held page cursors resolve to
  `StaleHistorySessionError` and the panel’s existing recovery restarts the walk.
  Status invalidation signals that reset; it does not implement a second one; and
- after timeout or truncation, suspend automatic retries until manual refresh or a later
  panel activation.

Manual refresh remains available in the Changes header.
It refreshes status only; the existing History refresh retains its own semantics.
A future combined repository refresh command may coordinate them, but this plan does not
invent one.

### Failure behavior

The status route follows existing Git route conventions:

- non-repository, missing Git, or non-root served paths return the established negative
  envelope with HTTP 200;
- malformed generations, scopes, or entry IDs return 400 without echoing untrusted
  values;
- a valid entry that disappeared or changed generation returns 409 `stale_status`;
- an unknown current entry returns 404;
- timeout returns 504;
- Git or parse failure returns a generic 500/502 envelope without stderr or absolute
  paths; and
- partial status returns 200 with `truncated: true` and a warning, because complete
  records remain useful.

The Changes and History sections render failure independently.
The selected main-pane diff uses the existing diff availability and plugin-error
components rather than a status-specific error design.

### Security and read-only guarantees

- Every Git command uses `create_subprocess_exec` with a fixed argv and no shell.
- The status capability gates on Git 2.36 or newer, forces `core.fsmonitor=false`, and
  pins `core.hooksPath` to a package-owned directory containing no recognized Git hook
  names so a read cannot start a daemon or execute a repository-configured hook.
- The status response never exposes the absolute root or Git directory.
- A comparison request accepts an entry ID from a validated current status snapshot, not
  an arbitrary revision or pathspec.
- Git path arguments still follow `--` defensively.
- Worktree reads use the package’s safe-path helpers and bounded reads.
- Symlink comparison uses `lstat` and `readlink`; it never follows a link to acquire
  diff content.
- External diff and textconv helpers are disabled.
- Optional locks and credential prompts remain disabled.
- Git stderr remains log-only because it can include absolute paths.
- Filenames, refs, warnings, and status labels are text-content escaped before DOM
  insertion.
- No route writes the index, worktree, refs, config, cache, or temporary comparison
  file.

### Design-system changes

Implementation adds a **Git Working Changes** subsection to `docs/design-system.md`. It
defines:

- Changes and History as peer top-level disclosures;
- the fixed status-group order and group-count grammar;
- `.git-status-list` as a navigational row collection;
- row anatomy: badge, basename, parent, rename source, and optional stats;
- selection, hover, focus, pending, stale, clean, partial, and error states;
- narrow-pane truncation and tooltip behavior;
- the accessible name for status, scope, full path, and rename source;
- the non-color status-letter mapping;
- keyboard and disposal behavior; and
- the rule that status diff content uses the existing diff surface unchanged.

The visual mapping reuses existing tokens:

| State | Token or primitive |
| --- | --- |
| Added and untracked | `--status-success` |
| Deleted | `--status-error-strong` |
| Conflict | `--status-warning-strong` plus `U` and conflict text |
| Rename/copy secondary cue | `--status-info` |
| Modified/type changed | ordinary `--text` |
| Parent path and clean metadata | `--muted` |
| Hover | `--hover-bg` |
| Selected row | existing Git/history selection treatment |
| Disclosure | shared section-disclosure chevron and motion |
| Row geometry | `--ui-row-height` and existing nav typography |

No local green, red, blue, or warning literal is allowed.
A new semantic color token is added only if contrast measurements prove the existing
vocabulary cannot express a state.

`tests/test_design_vocabulary.py` registers status rows beside Files and Git history in
the navigational-row check, registers the new disclosures in the chevron/row contract,
and pins the token mapping and non-color badges.

### Asset loading and browser ownership

`git-panel.js` remains the DOM and network owner.
A small strict `git-status-model.js` module owns pure grouping, row identity checks,
route-to-selection matching, and render-model helpers so they can be tested without a
browser.

The new module is **on demand**: it loads after repository discovery when the Git tab is
first shown or a status route must be restored.
It does not enter the shell’s eager path.
Status and diff-plugin assets prepare concurrently after a status row is selected.

Every status listener, abort controller, invalidation subscription, scheduled refresh,
and mounted diff handle has one disposal path.
Replacing the served root or leaving a status selection cannot let an old response paint
into the new root.

### Components and files

**Server and model**

- `metabrowser/git/status.py` — raw porcelain-v2 records, byte-safe parser,
  normalization, group projection, generation, clean predicate, and service.
- `metabrowser/git/status_coordinator.py` — in-flight coalescing, lazy targeted
  invalidation, debounce, SSE event, and disposal.
- `metabrowser/git/process.py` — already provides `spawn_git_process` and
  `terminate_git_process`; status adds record framing above them, not a new primitive.
- `metabrowser/git/capabilities.py` — cached Git-version parsing and the status safety
  gate.
- `metabrowser/data/no-hooks/README.md` — a shipped directory with no recognized Git
  hook names, used as the safe `core.hooksPath` target and checked in wheel inspection.
- `metabrowser/git/wire.py` — status snapshot/group/entry shapes and validators.
- `metabrowser/git/routes.py` — `GET /api/git/status` and common failure mapping.
- `metabrowser/diff/adapters/git_worktree.py` — one validated status entry to File Diff
  Format.
- `metabrowser/builtin_plugins/diff/sidekick.py` and `manifest.toml` — the
  `working-tree` data hook.
- `metabrowser/settings.py` — measured server and client settings only.
- `metabrowser/events.py` and `metabrowser/events_route.py` — typed `git.status-change`
  delivery through the existing event plane.

**Browser**

- `static/git-status-model.js` — strict, pure status render model.
- `static/git-panel.js` — sections, fetching, refresh, row DOM, selection, disposal,
  route restoration, and history coordination.
- `static/git-history-window.js` — the existing virtualized history window.
  Status does not modify it, but the panel restructuring must respect its scroll
  contract; see
  [Changes above a virtualized History](#changes-above-a-virtualized-history).
- `static/navigation.js` — `statusHref` and `parseStatus`.
- `static/types.d.ts` — one authoritative browser wire and runtime shape.
- `static/styles.css` — status component layout using existing tokens.
- `static/perf.js` — interaction attribution for status acquisition and one-file diff
  readiness where the existing generic spans cannot distinguish them.

**Documentation**

- `docs/design-system.md` — Git Working Changes.
- `docs/architecture.md` — status browser route in the URL grammar.
- `docs/project/architecture/arch-views-models-routes.md` — status model, browser route,
  and data routes.
- `docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md` —
  cross-reference the shared clean predicate without merging the features.
- `CHANGELOG.md` — user-visible Git panel and status route.

Adding the new data hook does not change the public plugin SDK and does not require a
`PLUGIN_SDK_VERSION` bump.
It is a built-in plugin route shipped with its only caller.

## API Changes

### `GET /api/git/status`

Positive response shape:

```json
{
  "is_repo": true,
  "head": {
    "ref": "refs/heads/main",
    "revision": "0123456789abcdef0123456789abcdef01234567",
    "detached": false,
    "unborn": false
  },
  "generation": "sha256:...",
  "groups": [
    {
      "scope": "unstaged",
      "entries": [
        {
          "id": "...",
          "scope": "unstaged",
          "kind": "modified",
          "index_status": ".",
          "worktree_status": "M",
          "path": "src/example.py",
          "entry_type": "file",
          "availability": "ready"
        }
      ]
    }
  ],
  "totals": {
    "entries": 1,
    "paths": 1,
    "exact": true
  },
  "truncated": false,
  "rename_similarity": 50,
  "submodule_policy": "..."
}
```

The example is illustrative; the TypedDict and validator are authoritative.
Conditional path-byte, old-path, mode, object-ID, conflict, similarity, and submodule
keys appear only where their record kind permits them.

The route supports `If-None-Match` over the status generation and returns 304 only after
the coordinator has established that no relevant invalidation occurred.
It does not serve a stale TTL entry merely because its wall-clock age is small.

### `GET /api/plugin/diff/working-tree`

Required query fields:

- `entry`: full status entry ID;
- `generation`: full status list generation.

The response is File Diff Format v1 narrowed to exactly that status comparison.
The standard built-in-plugin error envelope carries malformed, missing, stale, timeout,
and failed states.

### Browser route

`/status/<scope>/<entry-id>` restores the Git tab, current status, row selection, and
main-pane one-file diff.
It is a live address: reload resolves the current entry and reports stale if the working
state moved. It never implies immutable content the way `/commit/<revision>` does.

## Implementation Plan

Three phases: a measurement gate, a backend, and the browser delivery.
The gate is small and produces no code, but it is listed as a phase because its output
is the set of constants the other two are built on.

### Phase 0: The measurement gate (`mb-r5gn`)

This is a separate phase, not the first two items of the next one, because measurement
that shares a bead with the code it constrains gets done to justify that code rather
than to choose it — and its result is never separately reviewed.

- [ ] Build the dirty-tree fixture corpus and benchmark command covering every state in
  the special-case table, including the stat-dirty content-identical population.
- [ ] Record status and one-file-diff latency, bytes, retained memory, and
  representative browser row cost.
- [ ] Close the three [open decisions](#open-decisions): the submodule inspection
  option, the entry/byte/timeout/debounce/row budgets, and whether copy detection earns
  its cost.

**Acceptance boundary:** every constant Phase 1 will hard-code exists as a recorded
measurement with the command that produced it, and the three gate decisions are written
down with their evidence.
If a complete `--untracked-files=all` status cannot be bounded usefully, this phase ends
in a return to design review rather than in a chosen number — which is a real possible
outcome and the reason the gate is separable at all.

### Phase 1: Measured status and comparison backend (`mb-u4mf`)

Starts from the constants Phase 0 chose; it does not produce them.
- [ ] Extract the shared raw Git path codec from the immutable diff adapter.
- [ ] Add cached Git-version parsing and the Git 2.36 status-safety gate; keep
  repository discovery and History usable below it.
- [ ] Frame porcelain records over the existing `spawn_git_process` seam without
  weakening its environment, timeout, output, cancellation, stderr, or reaping rules.
- [ ] Implement strict incremental porcelain-v2 parsing for header, ordinary, rename,
  copy, unmerged, untracked, and ignored records.
- [ ] Implement `GitStatusService`, canonical sorting, raw-to-normalized projection,
  deterministic IDs, list generations, the clean predicate, and concurrent-request
  coalescing.
- [ ] Add status TypedDicts and runtime validators.
- [ ] Add `GET /api/git/status`, conditional requests, negative envelopes, typed partial
  results, and generic failure mapping.
- [ ] Implement `GitWorkingTreeDiffSource` for staged, unstaged, untracked, conflict,
  binary, symlink, submodule, too-large, and stale cases.
- [ ] Add the built-in diff `working-tree` data hook and keep the immutable comparison
  hook unchanged.
- [ ] Validate every produced document against the File Diff Format schema and apply
  oracle where both sides can be reconstructed.
- [ ] Add unit, property, fixture-repository, route, wire, timeout, truncation,
  cancellation, security, and linked-worktree tests.
- [ ] Update architecture maps for the new model and data routes; do not yet add the
  browser status route.
- [ ] Run `make verify` and land the backend with no user-visible half-control.

**Acceptance boundary:** The status endpoint losslessly and correctly distinguishes all
modeled Git states, a partially staged path produces two entries, every selectable entry
yields one valid bounded File Diff Format document or an explicit availability, and no
operation changes `git status --porcelain` or index metadata.

### Phase 2: Git panel, live invalidation, and delivery (`mb-vibn`)

- [ ] Add the status URL codec and restore path.
- [ ] Add the strict, on-demand `git-status-model.js` asset and browser wire types.
- [ ] Restructure the Git panel into Changes and History without changing history graph
  topology, paging, hover, or commit-detail behavior.
- [ ] Render clean, dirty, partial, loading, stale, timeout, and failed Changes states.
- [ ] Render fixed-order group disclosures and accessible flat status rows, including
  duplicate staged/unstaged paths, rename identity, conflicts, submodules, and path edge
  cases.
- [ ] Implement status-row navigation through the shared route, preview-claim,
  readiness, diff-plugin, and disposal lifecycles.
- [ ] Add the roving-tabindex and proportional-update keyboard contract and register the
  collection in the maintained design check.
- [ ] Add `GitStatusCoordinator`, lazy Git-control-file watching, working-tree
  invalidation, SSE delivery, measured debounce, hidden-panel staleness, and retry-storm
  suppression.
- [ ] Coordinate `HEAD` invalidation with the existing history reset instead of adding a
  second history refresh implementation.
- [ ] Add manual Changes refresh and preserve the existing History refresh.
- [ ] Add performance attribution for first status row, status-row acknowledgement, File
  Diff Format readiness, and painted one-file diff.
- [ ] Update the design system, URL grammar, architecture map, repository-cache
  cross-reference, roadmap, and changelog.
- [ ] Add DOM and real-browser tests for panel structure, keyboard, focus, route reload,
  retained-content handoff, invalidation, disposal, themes, narrow panes, and reduced
  motion.
- [ ] Run `make verify`, review the full branch diff, and complete the manual visual and
  interaction matrix before landing.

**Acceptance boundary:** Opening the Git tab in a dirty repository presents correct
groups above intact history; every navigable row opens the right single-file diff and
survives reload; external edits and Git operations refresh without races or request
storms; a clean cached checkout stays clean; and the automated plus manual gates pass.

## Testing Strategy

### Parser and model tests

- Feed porcelain-v2 bytes in every chunk boundary, including between the two paths of a
  rename record.
- Cover every ordinary `X` and `Y` kind, all seven conflict codes, untracked and ignored
  records, submodule flags, modes, SHA-1 and SHA-256 object IDs, unborn and detached
  branch headers, and unknown optional headers.
- Cover spaces, tabs, newlines, quotes, backslashes, Unicode, invalid UTF-8, and long
  paths.
- Reject malformed fields, partial records, duplicate IDs, invalid group order,
  inconsistent counts, and impossible conditional fields.
- Property-test chunking and parse/serialize normalization: chunk boundaries and Git
  record order cannot change the normalized snapshot or generation.

### Real repository tests

Build repositories under `tmp_path` with the real Git executable for:

- clean and dirty linear histories;
- partially staged content;
- staged and unstaged add/modify/delete/type-change states;
- rename plus later edit;
- intent-to-add;
- an unborn branch with staged files;
- binary, executable, symlink, and submodule entries;
- each unmerged state constructed through real merges or index stages;
- sparse checkout;
- linked worktrees with distinct indexes; and
- concurrent changes during a delayed status or diff command.

Before and after every read flow, capture authoritative status and index identity.
The test fails if Metabrowser changes either.

### File Diff Format tests

- Validate every status document against the checked-in JSON schema and Pydantic model.
- Reconstruct left and right content, apply the document to the left through the oracle,
  and compare with the right for ready text cases.
- Assert one-file totals, empty-side semantics, modes, rename sides, binary
  availability, no-newline markers, and mutable snapshot generations.
- Assert external diff and textconv commands configured in repository attributes are
  never executed.
- Assert stale-side races return stale rather than a mixed or cached document.

### Route and security tests

- Cover repository-root gating and every existing negative reason.
- Cover ETag/304, malformed IDs, malformed generations, unknown entries, moved entries,
  stale generations, timeout, partial status, parser failure, and generic error bodies.
- Cover standard, Apple, Windows, and vendor-suffixed Git version strings, the 2.36
  boundary, and History remaining available when status is unsupported.
- Prove no absolute path or Git stderr reaches JSON.
- Prove entry IDs, not display paths, select the diff and that `--` precedes any path.
- Prove symlinks cannot acquire content outside the served root.
- Configure an executable fsmonitor hook and executable diff/textconv helpers that write
  sentinels; prove no status or comparison path invokes them.

### Browser model and DOM tests

- Cover the two top-level sections, fixed group order, omitted empty groups, clean and
  partial states, counts, duplicate paths, rename rows, badges, and accessible names.
- Cover route encoding/parsing, reload restoration, stale routes, selection isolation,
  retained preview, and plugin failures.
- Cover roving Tab order, Arrow movement, Enter, Space, pointer activation, clamped
  edges, key repeat, focus preservation, and proportional row mutation.
- Cover disclosure ARIA, keyboard reachability, reduced motion, selection, hover, and
  both themes.
- Cover listener, timer, fetch, and mounted-view disposal when the panel or root
  changes.

### Real-browser and performance tests

The headed matrix includes clean, ordinary dirty, partially staged, conflicted,
truncated, and externally changing repositories at wide and narrow pane widths in both
themes. It records first status row, row acknowledgement, diff readiness, painted
readiness, DOM size, heap, and request counts.

The committed performance gate uses the measured corpus and budgets selected in Phase
1. It must detect an O(files × subprocesses) one-file click, unbounded DOM growth,
   automatic refresh storms, eager status work before the Git tab is used, and retained
   listeners after disposal.

`make verify` is required at the end of each phase.

## Rollout Plan

There is no compatibility flag.
The routes and assets are internal and ship together.

Phase 1 lands backend capability with tests and architecture documentation.
Phase 2 registers the visible route and panel.
On release:

- non-repositories behave exactly as today;
- clean repositories gain only a compact Changes state;
- dirty repositories gain grouped, read-only rows;
- cached repositories normally display clean and use the same service for integrity;
- status failure leaves History usable; and
- no mutation control appears.

The changelog calls out the new read-only status browsing and live route.
If telemetry or local performance traces show the measured bounds are wrong, change the
constants with new evidence; do not add an undocumented hidden fallback or silently omit
rows.

## Deferred Work

These are follow-on designs, not unfinished parts of the baseline:

- three-way base/ours/theirs conflict rendering and resolution;
- status tree projection and sorting preferences;
- file-tree and tab decorations;
- ordinary-file dirty gutters and inline previews;
- stage, unstage, discard, partial stage, commit, and stash actions;
- provider-aware pull-request working state; and
- a repository chooser that includes dirty/clean summary metadata.

Each mutating feature must start from the trusted-local editing and action contracts.
None is authorized by the read-only status service.

## Open Decisions

The product and model decisions are closed by this plan.
Phase 1 has three evidence gates whose outcomes become recorded implementation facts:

1. the explicit submodule inspection option;
2. the status entry, byte, timeout, debounce, and browser row budgets; and
3. the rename similarity threshold, plus whether copy detection is worth its cost.

Gate 3 has a fixed default and a narrow question.
The default is renames only, for the reasons in
[Rename and copy policy](#rename-and-copy-policy).
The question is whether `-c status.renames=copies` measures cheaply enough on the corpus
to be worth losing explicit similarity control and accepting a per-acquisition candidate
scan. If it does not, `C` stays parser-level coverage and the `/commit` versus `/status`
difference is documented rather than closed.

If measurement cannot support a complete `--untracked-files=all` status within a useful
bound, the phase must return to design review.
It may add an explicit partial/untracked policy, but it must not silently switch to
directory placeholders or hide untracked files while claiming complete status.

## References

- Git-status implementation epic: `mb-097x`
- [Git-status research](../../research/research-2026-08-26-git-status-and-dirty-working-trees.md)
- [Git graph and API](plan-2026-08-06-git-graph-view.md)
- [General diff rendering](plan-2026-08-17-general-diff-rendering.md)
- [Git revision navigation performance](plan-2026-08-25-git-revision-navigation-performance.md)
- [Unbounded logical Git history](plan-2026-08-25-unbounded-virtualized-git-history.md)
- [Repository library and Git URL opening](plan-2026-08-11-open-repo-from-git-url.md)
- [File Diff Format v1](../../architecture/file-diff-format/file-diff-format.md)
- [Diff sources, context, and anchoring](../../architecture/file-diff-format/diff-sources-and-anchoring.md)
- [Views, models, and routes](../../architecture/arch-views-models-routes.md)
- [Design system](../../../design-system.md)
- [Git status documentation](https://git-scm.com/docs/git-status)
- [Git diff documentation](https://git-scm.com/docs/git-diff)
- [Git `core.fsmonitor` documentation](https://git-scm.com/docs/git-config#Documentation/git-config.txt-corefsmonitor)
- [VS Code source-control overview](https://code.visualstudio.com/docs/sourcecontrol/overview)
- [VS Code staging and diff workflow](https://code.visualstudio.com/docs/sourcecontrol/staging-commits)
- [Pinned VS Code Git status acquisition](https://github.com/microsoft/vscode/blob/84ef3481c697a6bdf3bdb5777c50ba54346a1afe/extensions/git/src/git.ts#L2738-L2815)
- [Pinned VS Code status grouping](https://github.com/microsoft/vscode/blob/84ef3481c697a6bdf3bdb5777c50ba54346a1afe/extensions/git/src/repository.ts#L3020-L3095)
- [Pinned VS Code change-side resolution](https://github.com/microsoft/vscode/blob/84ef3481c697a6bdf3bdb5777c50ba54346a1afe/extensions/git/src/repository.ts#L590-L692)
- [Pinned VS Code refresh lifecycle](https://github.com/microsoft/vscode/blob/84ef3481c697a6bdf3bdb5777c50ba54346a1afe/extensions/git/src/repository.ts#L3176-L3227)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
