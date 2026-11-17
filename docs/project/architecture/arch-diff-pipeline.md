# Diff Pipeline

**Status:** Implemented: the patch-file and Git revision sources, the apply oracle,
manifest-first hydration on the server and in the page, the comparison caches, and the
rendered Markdown projection on a pull request’s Changes.
Planned: working-tree and index sources, in the
[Git status plan](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md);
anchoring a patch file to a repository; and context expansion, in the
[general diff rendering plan](../specs/active/plan-2026-08-17-general-diff-rendering.md).

[File Diff Format v1](file-diff-format/file-diff-format.md) defines what a comparison
document is. This document covers where documents come from, how much of one is sent and
drawn at a time, what is kept, and the rendered view of a Markdown change.

## Three Stages

Viewing a diff is three separable stages:

1. **Acquisition** obtains the raw material: a `.patch` file, two Git revisions, or a
   pull request’s commits in a repository store.
2. **Modeling** converts it to a `ChangeSetDocument` and validates it.
3. **Rendering** projects the document.
   The renderer never learns which source produced it.

The stages compose because everything converges on the format, and because unified patch
text is itself a convergence point: Git emits it for any pair of trees, GitHub serves it
for any pull request, and both parse through `parse_unified_patch`. The format has no
Git vocabulary, and Git is one source of it, not a substrate.
The GitHub plugin’s records refer to Git object IDs and add nothing to the format.

## The Source Port

`DiffSource` in `diff/adapters/base.py` has no source-specific vocabulary: `resolve` an
intent to a `ResolvedComparison`, list its `manifest`, give one `file_patch`, and stream
one side’s `content`. An intent is adapter-specific plain data; everything a source
returns is File Diff Format.
There is no source registry: callers construct the source they need, so the port, not a
table, is the contract.

Two sources exist:

- **`diff/adapters/patch_file.py`** parses a `.patch` or `.diff` with no repository,
  subprocess, or network.
  Malformed input is a value: a section it cannot model is left out and named, and a
  document it cannot model at all degrades to an empty one that says why.
- **`diff/adapters/git.py`** (`GitDiffSource`) compares revisions at a `GitLocation`.
  One revision compares against its first parent, and two endpoints compare directly or
  from their merge base.
  It lists changes with one `git diff --raw --numstat -z`, and its patches come from a
  path-limited `git diff` fed through the patch-file parser, so Git’s own output must
  round-trip through the neutral model.
  A comparison the diff plugin’s route asks for lists its files and prints its patch in
  one run, within `MAX_LISTED_PATCH_BYTES`, and Git stops once the patch passes that
  size. That run passes `--no-textconv`; where the configuration names a textconv driver,
  the page’s files are diffed in a run of their own, with their drivers
  (`diff/adapters/textconv.py` keeps that answer per configuration).
  On a store it reads blobs through the shared batch readers.

## Where Documents Come From

| Path | Pipeline | Status |
| --- | --- | --- |
| A patch file | `.patch` or `.diff` → patch source → render | Implemented: a folder-like entry in the tree, and `metab --diff FILE` |
| Git revisions | Revision or pair → Git source → render | Implemented: the Commits tab, and `metab --diff A..B`, a single revision, and `--diff-check` |
| A pull request’s patch | GitHub’s `.diff` download → a patch file | Implemented, as a patch file |
| A pull request over Git | Its head fetched into the store → merge base → Git source | Implemented: the pull-request page’s Changes |
| Uncommitted states | Working tree or index against `HEAD` → Git source | Planned |
| A patch anchored to a repository | A patch file plus a claimed base revision → validate → enrich | Planned; the oracle it needs is implemented |
| Document edit history | Editor sessions → a future source | No source; the format has room for one |

A pull request’s `.diff` and a merge-base comparison of the same commits describe the
same changes but are not the same document.
The patch source emits `patch` snapshots and `empty` content references, and shows a
type change as a deletion and an addition, because that is what patch text holds.
The Git source emits commit IDs and `git_object` content references and folds the pair
into one `type_changed` entry.

## Adding a Source

A new source answers four questions before it is written, because each is expensive to
retrofit:

1. **What is its identity?** Use content-addressed IDs where the source has them.
   Where it does not, as for a working tree or an index, manufacture one and say what it
   covers. The format reserves `generation` on `SnapshotRef` and `ContentRef` for such an
   identity, and no source sets it yet.
   A manufactured identity is never an immutable cache key.
2. **When does that identity go stale, and how is it detected?** A source over mutable
   state samples its identities before and after reading, and answers the `stale`
   availability rather than a document that mixes two states.
3. **What are its snapshot kinds?** `SnapshotKind` already has kinds for an index and a
   working tree; a new kind is a format change.
4. **What does it answer when it cannot produce?** `Availability` is the whole set of
   honest answers. Silently substituting an inferior rendering is not one.

What binds all four: no source-specific field enters File Diff Format.
Something the format has no room for belongs in the source’s own response beside the
document.

## Anchored and Unanchored Comparisons

A bare patch is self-contained but context-blind: it carries hunk-neighborhood context,
paths, and sometimes abbreviated blob IDs.
The patch source records this as an **unanchored** comparison.
An **anchored** comparison names real trees, as the Git source’s does.
A repository context gives a comparison whole files for Before and After, exact totals
and rename scores, folded type changes, and a computed merge base instead of a trusted
one.

**The apply oracle** decides whether a document matches its trees.
`apply_change_set` in `diff/apply.py` replays a hydrated document against a base tree
and either reproduces the target tree byte for byte, modes and entry types included, or
refuses with the first mismatch.
`metab --diff A..B --diff-check` runs it and reports the tree hashes it compared.

Anchoring a foreign patch is planned on that oracle, in two levels by cost: compare the
object IDs the patch claims against the repository first, then replay it in full, and
upgrade a clean result to an anchored document.

## Hydration

A comparison is sent manifest first and patches later, and every file states its
availability, so an absent patch is never an empty one.

**On the server**, the comparison route of the diff plugin
(`GET /api/plugin/diff/comparison`, in `builtin_plugins/diff/sidekick.py`) lists the
manifest, up to `MAX_MANIFEST_FILES` in `diff/adapters/git.py`, and hydrates the first
`MAX_HYDRATED_FILES` ready files from one diff run and one parse.
The rest are `deferred` and load alone when the reader reaches them.
A pull request’s first answer hydrates fewer, `INITIAL_PULL_FILES` in
`builtin_plugins/github/sidekick.py`. `MAX_FILE_PATCH_BYTES` bounds one file’s patch and
what one run hydrates: one file past it is `too_large`, and a file that would take a run
past it is `deferred`. Each constant’s comment records the measurement that set it.

**In the page**, `builtin_plugins/diff/diff-view.js` keeps every file’s bar in the page
and draws rows only near the viewport:

- **The mount** draws rows for the ready files within the pane and one screen more
  (`firstScreenBudget`). Later ready files are bars that reserve their height from
  `patchRows` until they are drawn.
- **`createHydrationScheduler`** asks for one deferred file at a time, from the top of
  the viewport through `HYDRATION_AHEAD_PX` below it, and draws at most one file per
  frame. A file jump goes first and cancels other requests, and a burst of jumps waits
  `JUMP_QUIET_MS` and asks for the file it rests on.
- **A collapsed run** mounts only its visible prefix; expanding it adds
  `FOLD_MATERIALIZATION_BATCH_ROWS` rows per task, and collapse, reprojection,
  replacement, and disposal cancel pending batches.
  The performance loop’s browser profile gates `collapsed_diff_rows_materialized` at
  zero.
- **A layout switch** reprojects `LAYOUT_PROJECTION_BATCH_FILES` files per task and
  drops stale batches when a newer selection arrives.
  [The layout benchmark](../../../explorations/diff-layout/README.md) holds the fixture.
- **Intraline refinement** counts its edit-distance work and falls back to positional
  rows past `INTRALINE_WORK_BUDGET`, which bounds the pathological cost without a second
  file-size limit.
  [The intraline benchmark](../../../explorations/diff-intraline/README.md) holds the
  evidence.

Find in page finds what is drawn and every file’s path, since every bar is in the page.
A list of the comparison’s files reaches one through the view’s handle:
`scrollToFile(path)` puts the file at the top of the pane, expanded, and holds it there
as files above fill in, until the reader scrolls; `fileForPath`, `currentFile`, and
`onCurrentFile` answer which file a path names and which is on screen.
Each answer is typed, because a list from GitHub and a comparison computed here can
differ. `tests/dom/diff-file-jump-session.js` pins the contract, and
[exp-040](../../../explorations/performance-loop/experiments/exp-040-files-changed-recomputes-the-whole-patch-per-request.md)
holds its budgets.

Syntax tokens, intraline ranges, and split-row pairings are browser enrichments derived
from the line records (`diff-syntax.js`, `diff-intraline.js`, `diff-render-model.js`),
not format fields, so a palette, algorithm, or layout change cannot invalidate a
comparison.

## Caches

A local repository, a mirror, and a pull request all reduce to object IDs that the same
Git source compares.
Only the repository store must be kept; every comparison kept beside it, on disk or in
memory, can be computed again:

- **The repository store** holds Git objects across sessions; see the
  [repository cache](arch-repository-cache.md).
- **The pull request’s manifest bank** (`builtin_plugins/github/pull_manifest.py`) keeps
  a prepared manifest beside the store after each fetch, in a fixed number of
  direct-mapped slots, so a fresh server skips the costly listing.
  A missing, stale, or corrupt slot is recomputed.
- **The server’s comparison cache** (`builtin_plugins/diff/comparison_cache.py`) keeps a
  store comparison’s resolution and manifest, and each encoded answer, in memory, keyed
  by the commit IDs and every request input the answer reads.
  Its entity tags are scoped to the build and the store, so a browser’s HTTP cache keeps
  them too. It keeps nothing for a served folder, whose answer can change with its
  working tree’s `.gitattributes`, `.git/config`, the reader’s Git configuration, or a
  replace ref; the module docstring lists what a store’s answer depends on and why each
  is covered.
- **The Commits panel’s cache** (`static/git-panel.js`) keeps each answered comparison
  whose revision is a full commit ID, so a revisited commit’s diff mounts with no
  request. It is bounded by `GIT_COMPARISON_CACHE_BYTES` of JSON, with a quarter for one
  answer, least recently used first, and is sized in a task after the one that hands the
  answer to the diff. Refresh, the panel’s teardown, and a history walk found stale clear
  it, and an answer requested before a clear is not kept.
  A folder’s answer kept here can outlive a change to its Git configuration until one of
  those clears.
- **A pull request page’s keep** (`createComparisonKeep` in
  `builtin_plugins/github/comparison-prefetch.js`) keeps each comparison a pull
  request’s page reads for the document rather than for one page, keyed by the
  comparison’s route and bounded by `KEPT_COMPARISON_CHARS`, so a revisit draws its Diff
  summary and mounts Changes with no request; see
  [The Comparison Keep](arch-github-pull-requests.md#the-comparison-keep).

A refusal is never kept, since a fetch can answer it.

## Markdown Projection

A pull request’s Changes shows a changed Markdown file as **Rendered** by default, with
**Source** for the exact diff.
`GET /api/plugin/github/pull-rendered-diff` answers one file’s projection, and
`builtin_plugins/diff/diff-markdown.js` mounts it.

`diff/markdown_projection.py` parses each side once with KPress’s own MarkdownIt core,
so a block’s source range is the map of the token that renders it, and renders every
top-level block from its own tokens through KPress’s sanitizer and the inert-HTML
hardening. `tests/test_markdown_diff_projection.py` checks the joined blocks against
KPress’s own render.
Changed words are marked by a bounded word diff.

- **Fallback:** a side with raw HTML other than comments, with footnotes, or past the
  projection’s budgets (`MARKDOWN_DIFF_MAX_BYTES` and the bounds beside it, each with
  its measurement) is refused, and the file shows Source.
  The projection renders with math and diagrams off and without code highlighting.
- **Hidden signature:** whatever a block’s source says that its render does not show,
  such as a link destination, a title, alt text, or a fence’s info string.
  A changed block whose hidden signature differs is flagged `source_only`, as is a file
  whose source changes include one with no visible counterpart.
  A flagged block never folds, and the page draws no note for it: Source is how a reader
  reaches such a change.
- **Off the server’s interpreter:** projections run in one long-lived child process
  (`diff/markdown_projection_worker.py`), started on the second projection or on a
  page’s prefetch, so a projection never holds the server’s GIL; the module records the
  measurement. Until the child is ready, projections run in a thread.
- **Paint:** a file on screen waits for its projection for the app’s loading-state delay
  with Source hidden; past it, Source paints first and Rendered replaces it when it
  arrives. Conversation prefetches the projections of the first screen’s files.

Markdown is the first format.
Another can supply an equivalent bounded, inert projection once its renderer can map
changes to source ranges.

## References

- [File Diff Format v1](file-diff-format/file-diff-format.md)
- [Git Reading and History](arch-git.md)
- [Source Sessions and Pins](arch-source-sessions-and-pins.md)
- [General diff rendering plan](../specs/active/plan-2026-08-17-general-diff-rendering.md),
  the design history of this pipeline
- [File patch formats](../research/archive/research-2026-08-19-file-patch-formats.md)
- [Rendering large content](../../large-content-rendering.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
