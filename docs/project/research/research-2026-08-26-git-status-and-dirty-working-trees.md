# Research: Git Status and Dirty Working-Tree Browsing

**Date:** 2026-08-26

**Author:** Joshua Levy (with LLM assistance)

**Status:** Complete

## Overview

Metabrowser already presents Git history and renders commit comparisons through File
Diff Format. This research asks how to add the other half of ordinary Git browsing: the
uncommitted state of a working tree.

The target experience is familiar from VS Code.
The Git panel lists unresolved conflicts, staged changes, unstaged changes, and
untracked files. Selecting one row opens a single-file diff in the main content pane.
The first release remains read-only: it observes the index and working tree but does not
stage, discard, commit, or resolve anything.

This work is separate from the repository cache.
A cache checkout is intended to remain clean and read-only, so its status section will
normally report a clean tree.
Ordinary local repositories are often dirty, however, and use the same Git panel,
comparison renderer, and repository identity.
The status model should therefore be general Git infrastructure that the cache can also
use for integrity checks.

## Questions to Answer

1. Which Git interface gives a stable, complete, byte-safe status model?
2. How should staged, unstaged, untracked, renamed, conflicted, and submodule states be
   represented without losing Git’s two-layer index/worktree semantics?
3. Which VS Code source-control patterns should Metabrowser adopt, and which are editor
   or mutation concerns that should remain out of scope?
4. How can a selected status row reuse File Diff Format and the existing diff plugin?
5. How should a live working tree refresh without presenting a mutable view as an
   immutable snapshot?
6. What bounds, security rules, accessibility behavior, and design-system changes are
   needed before implementation?

## Scope

The research covers a read-only status list, one-file comparisons, refresh and
invalidation, Git edge cases, and integration with the existing Git panel and diff
renderer. It inspects VS Code’s Git extension and SCM workbench at a pinned source
revision, Git’s official status and diff contracts, and Metabrowser’s current Git and
File Diff Format implementations.

It does not design staging, partial staging, discard, checkout, commit creation, merge
resolution, inline editor gutters, or hosted-provider data.
Those features require mutation or richer editor contracts and should not be smuggled
into a read-only status surface.

## Findings

### Git status is two comparisons, not one label per file

Git status describes three classes of path:

- differences between `HEAD` and the index;
- differences between the index and the working tree; and
- untracked paths that are absent from the index.

The two characters in Git’s `XY` status are independent outside an unresolved merge: `X`
describes the index and `Y` describes the working tree.
A file may therefore appear in both a staged and an unstaged group.
Flattening `MM` to one “modified” row would hide the fact that the next commit contains
one version while the working tree contains a later version.

The useful projection is:

| Surface group | Comparison | Typical source statuses |
| --- | --- | --- |
| Conflicts | Unmerged index stages plus the working result | `DD`, `AU`, `UD`, `UA`, `DU`, `AA`, `UU` |
| Staged Changes | `HEAD` or the empty tree → index | nonblank `X` |
| Changes | index → working tree | nonblank `Y` |
| Untracked | empty → working tree | `??` |

One parsed record may project into two rows.
The projection must preserve that duplication rather than deduplicate by path.

### Porcelain v2 is the right acquisition contract

VS Code currently runs `git status -z -uall` and parses porcelain v1. It streams NUL
records, sets `GIT_OPTIONAL_LOCKS=0`, and stops after a configurable number of entries.
That implementation is proven, but Metabrowser should use
`git status --porcelain=v2 -z --untracked-files=all` for a new parser.

Porcelain output is explicitly stable across Git versions and independent of user
display configuration.
Version 2 additionally includes the information Metabrowser’s diff model already
understands:

- `1` records for ordinary tracked changes;
- `2` records for renames and copies, including the original path and similarity;
- `u` records for unresolved paths, including stages 1, 2, and 3;
- `?` records for untracked paths;
- modes for `HEAD`, the index, and the worktree;
- object IDs for `HEAD` and the index; and
- explicit submodule commit, tracked-content, and untracked-content flags.

With `-z`, paths are emitted as raw bytes and separated by NUL rather than quoted.
The current `run_git` API already returns bytes, and File Diff Format already carries a
display path plus optional base64 for paths that are not valid UTF-8. The new parser can
reuse that path convention instead of introducing a lossy string-only boundary.

Tracked porcelain-v2 records have undefined ordering.
Any generation digest or test fixture must normalize and sort parsed records; it must
not hash or snapshot the raw command order.

### Status command policy must be explicit

Several user Git settings can change status behavior.
A machine-facing acquisition command should choose its policy rather than silently
inherit it:

- request porcelain v2 and NUL framing explicitly;
- request individual untracked files with `--untracked-files=all`;
- omit ignored files;
- choose rename detection and its similarity threshold explicitly, aligned with the
  existing Git diff adapter;
- choose a submodule policy explicitly rather than inherit `diff.ignoreSubmodules` or
  `.gitmodules` display preferences; and
- continue using `--no-optional-locks` and `GIT_OPTIONAL_LOCKS=0` so observation does
  not refresh or lock the user’s index.

`git status` is not automatically inert because it is nominally read-only.
A configured `core.fsmonitor` may invoke an external hook, and a modern built-in
fsmonitor may start a background daemon.
Status acquisition must force `core.fsmonitor=false` and pin `core.hooksPath` to a
package-owned directory containing no recognized Git hook names.
Git 2.35.1 and older may interpret the boolean value `false` as a hook pathname, so the
status feature needs an explicit Git-version gate rather than an unsafe compatibility
fallback.
Git history may remain available when status reports `unsupported_git_version`.

The completeness-oriented submodule policy is to report the parent gitlink and its
porcelain-v2 state bits without recursively presenting nested files as members of the
parent repository. Whether the acquisition command should inspect nested dirty state or
ignore it for performance needs measurement on repositories with real submodule trees.
The API must state the chosen policy and surface a timeout or truncation honestly.

### VS Code’s resource grouping is the key pattern to adopt

At source commit
[`84ef3481c697a6bdf3bdb5777c50ba54346a1afe`](https://github.com/microsoft/vscode/commit/84ef3481c697a6bdf3bdb5777c50ba54346a1afe),
VS Code’s Git extension has four resource groups: merge, index, working tree, and
untracked. Its repository model first recognizes the seven unmerged `XY` combinations,
then independently projects `X` into the index group and `Y` into the working-tree
group. That is the correct behavioral precedent for partially staged files.

VS Code also separates resource identity from the content pair used to open it.
Its change resolver maps:

- index modifications and renames to `HEAD` versus the index;
- working-tree modifications to the index versus the filesystem;
- untracked files to an empty original versus the filesystem; and
- conflicts to index stages such as ours and theirs, with an optional merge editor.

Metabrowser should adopt the first three comparisons directly.
It should list conflicts with their precise conflict kind, but it should not pretend
that a two-way diff is a three-way resolution tool.
The baseline can render the working result against the stage-1 merge base when one
exists, or against empty for both-added conflicts, with a visible warning that the path
remains unmerged. A dedicated base/ours/theirs merge view belongs in a later plan.

### The VS Code refresh loop provides useful guardrails

VS Code watches both the working tree and relevant Git-control files.
It debounces filesystem events, throttles status runs, cancels superseded model updates,
waits until the repository is idle and the window is focused, and stops automatic
refresh for a repository that exceeded its status limit.
It also offers explicit refresh.

Metabrowser has a different lifecycle, but the same rules apply:

- load status only when the Git panel is first shown or a status URL is restored;
- coalesce concurrent callers around one in-flight status run;
- debounce working-tree and targeted Git-control-file events;
- cancel or discard superseded results;
- keep manual refresh available;
- stop automatic retry storms after timeout or truncation; and
- dispose every listener and pending request when the panel or served root is replaced.

A broad working-tree watcher alone is insufficient.
External `git add`, `git reset`, checkout, merge, or rebase operations may primarily
update the per-worktree index, `HEAD`, or operation markers.
Linked worktrees make a literal `.git/index` assumption incorrect.
Git paths must be resolved with `git rev-parse --git-path`, or through the repository
context that already understands linked worktrees.

### A live working tree is not an immutable snapshot

Commit comparisons are content-addressed.
Status comparisons are not: a user or tool can edit a file between list acquisition and
diff acquisition while its status remains `M`.

The API should make this difference explicit:

- a status response carries an opaque *list generation* derived from normalized status
  records, `HEAD`, and index identity;
- each row carries a deterministic ID derived from its scope and raw path identity;
- a diff request names the row ID and expected list generation, not an arbitrary Git
  pathspec;
- the server recomputes or revalidates the row before diffing;
- index and relevant filesystem metadata are sampled before and after materialization;
- if the row moved groups or either side changed during the read, the route returns a
  typed stale response and the browser refreshes; and
- successful documents carry index/worktree snapshot generations but never claim to be
  durable revision IDs.

This is optimistic consistency, not snapshot isolation.
Creating a frozen worktree copy for every click would make a read-only viewer slower and
would add cleanup and disk failure modes without protecting a mutation workflow that
Metabrowser does not own.

### File Diff Format already models the needed snapshots

File Diff Format v1 defines `commit`, `tree`, `index`, `worktree`, and `empty` snapshot
kinds. It can also identify Git-object, inline, or empty content.
No schema revision is needed for the baseline.

The existing immutable-revision adapter should stay intact.
A separate working-tree adapter can materialize exactly one selected row:

| Status scope | Left snapshot | Right snapshot | Acquisition |
| --- | --- | --- | --- |
| Staged | `HEAD` or empty | index | path-limited `git diff --cached` |
| Unstaged | index | worktree | path-limited `git diff` |
| Untracked | empty | worktree | bounded safe-path read; all text lines are additions |
| Conflict | stage 1 or empty | worktree result | bounded Git-object and safe-path reads, with an unmerged warning |

Git patch generation must pass `--no-ext-diff` and `--no-textconv`, and the shared safe
read profile must disable fsmonitor and hooks.
Repository-owned attributes or config may otherwise invoke an external helper during
what appears to be a read-only browser request.
The adapter should keep using the existing patch parser, manifest model, availability
states, content bounds, and diff renderer.

Untracked text needs no general diff algorithm: its old side is empty, so every line is
an addition. Binary, oversized, symlink, and submodule entries should use the same typed
availability and entry-type behavior as other File Diff Format sources.

### A status entry needs more than a display kind

The wire model should preserve Git facts and provide a normalized projection.
At minimum, each entry needs:

- a deterministic row ID;
- comparison scope (`conflict`, `staged`, `unstaged`, or `untracked`);
- normalized change kind and original kind when different;
- raw `X` and `Y` values for diagnostics and lossless round-tripping;
- current and original raw path identities with display/base64 forms;
- modes and available object IDs;
- rename or copy similarity;
- conflict kind and stage metadata for unmerged entries;
- entry type (`file`, `symlink`, or `submodule`);
- submodule state flags; and
- availability when the row can be listed but not rendered.

The browser should not reinterpret porcelain letters.
Group projection and normalized kind assignment belong in the Python status service and
its validators.

### Bounds must preserve complete records and honest state

Untracked discovery can dominate `git status` on a large tree.
VS Code streams status, kills the process after a default limit of 10,000 entries,
returns the complete prefix, and marks the repository as huge so filesystem events do
not trigger an automatic status loop.

Metabrowser’s current runner incrementally caps bytes but returns no data after an
overflow. Status needs a record-aware streaming path so it can stop at measured byte,
entry, or time bounds while retaining only complete records and reporting
`truncated: true`. The response cannot claim a total count after the producer is killed,
and a truncated empty prefix cannot be rendered as “clean.”

The project requires measurement before a bound becomes a product constant.
The implementation plan should add a dirty-tree corpus covering tracked changes, flat
and nested untracked populations, renames, binary files, submodules, and path edge
cases; record time to first record, completion time, output bytes, peak retained bytes,
and browser rows; then place the selected thresholds beside that evidence.

### The status list should share the Git tab, not replace history

The narrow Git panel should become two top-level disclosures:

1. **Changes**, always present after status loads, showing `Clean` or a count; and
2. **History**, preserving the existing graph and paging behavior.

Dirty Changes starts expanded.
Its nonempty subgroups appear in the fixed order Conflicts, Staged Changes, Changes, and
Untracked. A path that is staged and then edited appears once in Staged Changes and once
in Changes. Each group is a disclosure with a count.
The initial view is flat: basename first, parent path muted, original-to-new path for a
rename, and one letter badge that is not color-only.

Selecting a row opens the existing diff view narrowed to that file.
Status rows form a navigational row collection with the same roving-tabindex, Arrow
Up/Down, Enter, Space, selection, focus, hover, and proportional-update rules as Git
history. The new collection must be added to the maintained design-vocabulary check.

VS Code supports flat and tree projections, file decorations, inline editor gutters, and
mutation controls. Those are useful future options, not baseline requirements.
A flat grouped list fits the current panel and avoids introducing a second
directory-tree implementation before measurements show that one is needed.

### The design system can reuse semantic tokens

The status list needs a documented component vocabulary but no new color family:

- added and untracked use `--status-success`;
- deleted uses `--status-error-strong`;
- conflicts use `--status-warning-strong` plus an explicit `U` badge and text label;
- rename/copy may use `--status-info` as a secondary cue;
- modified and type-changed remain standard text unless contrast testing proves a new
  semantic role is necessary;
- selection, hover, focus, row height, disclosure chevrons, path typography, and change
  statistics reuse their existing primitives.

Color remains secondary to the status letter, group label, accessible name, and rename
text. Group headers use the section-disclosure contract.
Rows use the navigational-row contract.
The one-file diff remains the diff plugin’s surface, so addition/deletion fills, syntax
contrast, unified/split layout, and folding do not fork.

## Options Considered

### Option A: Porcelain v2 service plus File Diff Format adapter

**Description:** Parse stable NUL-framed porcelain-v2 records into a typed status
snapshot, project comparison rows server-side, and materialize selected rows through a
dedicated working-tree File Diff Format source.

**Advantages:**

- preserves index and worktree semantics;
- carries modes, object IDs, submodule state, conflicts, and raw paths;
- reuses the existing renderer and conformance model;
- keeps GitHub and cache policy out of the status contract; and
- supports linked worktrees and unborn branches without aliases or compatibility shims.

**Costs:**

- requires a new parser, wire validators, and record-aware status runner;
- requires explicit stale-result handling; and
- needs measured bounds before implementation constants are chosen.

### Option B: Copy VS Code’s porcelain-v1 resource model exactly

**Description:** Port `GitStatusParser` and the four resource groups directly.

**Advantages:**

- mature behavior and simple `XY` parsing;
- direct correspondence with VS Code source; and
- known streaming-limit pattern.

**Costs:**

- discards modes, index object IDs, detailed submodule state, and conflict-stage data;
- would require extra Git calls to construct File Diff Format sides; and
- would reproduce editor-specific URI conventions that Metabrowser does not need.

**Decision:** Use VS Code’s grouping and refresh patterns, not its narrower transport
record.

### Option C: Compare `HEAD` directly with the working tree

**Description:** List and diff the aggregate uncommitted result as one change set.

**Advantages:** Simple and superficially similar to a commit comparison.

**Costs:** Hides partial staging, cannot show what the next commit contains, mislabels
intent-to-add and staged deletions, and makes the status list disagree with Git.

**Decision:** Rejected.
It loses the core information the feature exists to present.

### Option D: Build a status-specific diff renderer

**Description:** Add a new server payload and browser view for working-tree patches.

**Advantages:** Could be tailored narrowly to one file.

**Costs:** Duplicates File Diff Format validation, syntax highlighting, layouts,
folding, availability, and future performance work; creates visual and behavioral drift.

**Decision:** Rejected.
Status is a new comparison source, not a new diff format.

### Option E: Freeze every selected file into a temporary snapshot

**Description:** Copy index and worktree content before rendering so every URL denotes
immutable bytes.

**Advantages:** Strong snapshot isolation.

**Costs:** Adds disk writes, cleanup, permissions, storage bounds, and failure states to
a read-only viewer; can still race before the copy; and makes ordinary clicks slower.

**Decision:** Rejected for the baseline.
Use optimistic revalidation and typed stale responses.

## Recommendations

1. Implement a core `GitStatusService` over porcelain v2, with byte-safe paths,
   server-side group projection, deterministic row IDs, normalized generation, and
   record-aware bounds.
2. Add a separate working-tree Git diff source that emits ordinary File Diff Format v1
   documents for one selected status row.
3. Extend the Git panel with Changes above History, fixed group order, manual refresh,
   and the shared navigational-row and disclosure contracts.
4. Add debounced live invalidation only after the baseline service and browser flow are
   measurable and correct.
   Watch both working-tree events and resolved Git control paths, and coalesce
   refreshes.
5. Keep all operations read-only.
   Defer stage, unstage, discard, commit, file editing, and three-way merge resolution
   to separately authorized plans.
6. Reuse the status service’s clean predicate for repository-cache integrity rather than
   keeping a second `git status` interpretation.

## Next Steps

- [ ] Land the phased plan linked below and create one implementation bead per phase.
- [ ] Build the dirty-tree fixture and benchmark corpus before selecting status entry,
  byte, timeout, debounce, or row-rendering constants.
- [ ] Implement and validate the porcelain-v2 parser before adding UI.
- [ ] Add the working-tree comparison adapter and prove its documents through the File
  Diff Format conformance and apply oracles.
- [ ] Add Changes to the Git panel, the canonical status route, browser lifecycle, and
  live invalidation in the phase that owns them.

## Methodology

The review used three kinds of evidence:

- Metabrowser source and architecture on the planning branch, especially
  `metabrowser/git`, `metabrowser/diff`, `static/git-panel.js`, File Diff Format, the
  route map, and the design system;
- a clean local checkout of `microsoft/vscode` pinned at
  `84ef3481c697a6bdf3bdb5777c50ba54346a1afe` (commit timestamp 2026-08-27T05:50:05Z),
  with the Git extension’s parser, repository model, resource resolver, quick-diff
  provider, settings, and watcher flow inspected directly; and
- current official Git and VS Code documentation for porcelain stability, diff endpoint
  semantics, source-control grouping, file diff behavior, and conflict UX.

No benchmark numbers from VS Code or another repository were adopted as Metabrowser
constants. VS Code’s 10,000-entry default is prior art, not local evidence.

## References

- [Feature plan: Git status and working-tree diffs](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md)
- [Git status documentation](https://git-scm.com/docs/git-status)
- [Git diff documentation](https://git-scm.com/docs/git-diff)
- [Git `core.fsmonitor` documentation](https://git-scm.com/docs/git-config#Documentation/git-config.txt-corefsmonitor)
- [VS Code source-control overview](https://code.visualstudio.com/docs/sourcecontrol/overview)
- [VS Code staging and diff workflow](https://code.visualstudio.com/docs/sourcecontrol/staging-commits)
- [VS Code merge-conflict workflow](https://code.visualstudio.com/docs/sourcecontrol/merge-conflicts)
- [VS Code streamed status acquisition](https://github.com/microsoft/vscode/blob/84ef3481c697a6bdf3bdb5777c50ba54346a1afe/extensions/git/src/git.ts#L2738-L2815)
- [VS Code status grouping](https://github.com/microsoft/vscode/blob/84ef3481c697a6bdf3bdb5777c50ba54346a1afe/extensions/git/src/repository.ts#L3020-L3095)
- [VS Code change-side resolution](https://github.com/microsoft/vscode/blob/84ef3481c697a6bdf3bdb5777c50ba54346a1afe/extensions/git/src/repository.ts#L590-L692)
- [VS Code status refresh lifecycle](https://github.com/microsoft/vscode/blob/84ef3481c697a6bdf3bdb5777c50ba54346a1afe/extensions/git/src/repository.ts#L3176-L3227)
- [File Diff Format v1](../architecture/file-diff-format/file-diff-format.md)
- [Diff sources, context, and anchoring](../architecture/file-diff-format/diff-sources-and-anchoring.md)
- [Git graph and API plan](../specs/active/plan-2026-08-06-git-graph-view.md)
- [General diff rendering plan](../specs/active/plan-2026-08-17-general-diff-rendering.md)
- [Earlier web diff architecture research](research-2026-07-17-web-diff-viewer-architecture.md)
- [Repository library plan](../specs/active/plan-2026-08-11-open-repo-from-git-url.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
