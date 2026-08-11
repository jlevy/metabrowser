# Feature: Git Graph Nav Panel and Git API

**Date:** 2026-08-06 (last updated 2026-08-09)

**Author:** Metabrowser maintainers

**Status:** Implemented; `make verify` green

## Overview

Metabrowser should show repository history as a second nav-panel tab beside Files.
The tab renders a commit graph in the layout VS Code uses for its built-in Source
Control Graph: one row per commit, a narrow left gutter of colored swimlanes drawn as
SVG, then reference badges, subject, author, and relative date.
Selecting a commit opens a commit-detail view in the preview pane listing the changed
files; selecting a changed file opens that file through the normal navigation path.

The server gains a dedicated Git endpoint collection under `/api/git/` with its own wire
model, kept separate from the tree, recent, and file endpoints.
The browser gains a swimlane layout module and a graph renderer, both ported from the
MIT-licensed VS Code implementation.

## Goals

- A Git tab in the nav panel, shown only when the served root resolves to a git
  repository, and lazily loaded on first selection like Recent
- A commit graph matching the VS Code Source Control Graph layout: 22 px rows, 11 px
  swimlanes, 4 px commit nodes, curved branch and merge paths, and a bounded
  colorblind-safe lane palette expressed as design tokens
- Reference badges for the current HEAD, local branches, remote branches, and tags, in
  VS Code’s precedence order
- Incremental paging: an initial page of commits, then further pages appended as the
  panel scrolls, with lane continuity preserved across page boundaries
- A hover card per commit carrying the full message and that commit’s files-changed,
  additions, and deletions
- A commit-detail view in the preview pane: metadata, references, full message, per-file
  change status with additions and deletions, and navigation to any changed file that
  still exists under the served root
- A `/api/git/` endpoint collection with typed wire models and a runtime validator,
  following the `wire_models.py` convention
- A data-driven nav-panel tab list in place of the hardcoded tab markup

## Non-Goals

- Diff rendering. No unified or side-by-side diff view, no diff parser, and no new diff
  file kind. Selecting a changed file opens its current contents in the ordinary preview.
- Incoming and outgoing changes.
  The synthetic ahead/behind rows VS Code draws above the graph are deferred; the
  upstream ref and merge-base resolution they need are not built.
- A reference filter or branch picker.
  The graph shows all references.
  Scoping the graph to one ref is deferred.
- Any write operation.
  Nothing in this feature stages, commits, checks out, fetches, or otherwise mutates the
  repository. The endpoint collection is read-only.
- Live graph updates over the event stream.
  Repository state is fetched on tab selection and on an explicit refresh.
  Wiring `.git` changes into the SSE bus is deferred.
- Submodule, worktree-list, and bare-repository presentation beyond not crashing.

## Background

### Where the layout comes from

The graph the user asked to reproduce is not part of the GitHub extension.
It is VS Code’s built-in Source Control Graph, which lives in core under
`src/vs/workbench/contrib/scm/browser/` and is MIT-licensed.
A shallow sparse checkout of `microsoft/vscode` is in `attic/vscode` for reference.

Three pieces matter:

- `scmHistory.ts` holds the whole graph.
  `toISCMHistoryItemViewModelArray` is the swimlane algorithm: it walks commits in topo
  order carrying an output-swimlane array forward as the next row’s input swimlanes,
  replaces a commit’s own lane with its first parent, and appends a new lane per
  additional merge parent.
  `renderSCMHistoryItemGraph` emits one small `<svg>` per row — vertical lines for
  pass-through lanes, curved paths for branch and merge, and a circle for the commit.
  Per-row SVG rather than one large canvas is what lets the graph virtualize inside an
  ordinary scrolling list.
- `media/scm.css` holds the row layout under `.history-item`: the graph gutter, the
  badge container, and the message and author truncation behavior.
  This is the source of the proportions the user liked.
- The bundled git extension supplies the data with a single
  `git log --topo-order -z --format=%H%n%aN%n%aE%n%at%n%ct%n%P%n%D%n%B`. The `%P` parent
  list is all the layout algorithm needs.

`scmHistoryViewPane.ts` is the view shell.
It is coupled to VS Code’s list and observable infrastructure and is a behavioral
reference only, not a porting target.

### Why the layout stays in the browser

The swimlane assignment is a pure function of the commit list and its ordering, and it
is naturally incremental: each page’s lanes continue from the previous page’s trailing
lane state. That makes it a rendering concern.

This repository has already settled the same question once.
`recent.py` returns a flat newest-first leaf list and leaves clustering to
`clusterRecentTreeJs`, with the layering rationale recorded in both places.
The Git panel follows that precedent: the server returns commits, parents, and
references; the browser assigns lanes and draws them.
The wire model stays free of presentation state, and the ported algorithm stays in the
language it was written for.

### Core, plugin, or both

The user asked whether this could ship as a plugin.
It cannot, as the plugin system stands.

The manifest contributes kind rules, views bound to a kind, and data hooks mounted under
`/api/plugin/<name>/<route>`. Every one of those extends the file-preview path.
There is no extension point for contributing a nav-panel tab, and no way for a plugin to
claim a top-level route collection.
A Git tab as a plugin would require new SDK surface first.

Building it in core is also the better fit on the merits.
The stated boundary keeps core consumer-agnostic and pushes domain schemas to plugins,
but git is not a consumer domain here — core already depends on it.
`ignore_filter.py` implements gitignore semantics, `tree.build_gitignore_check` performs
repository-root discovery and caches it per root, `watch_backends.py` re-derives
`gitignored` on every filesystem event, and the tree and recent wire models both carry a
`gitignored` flag. Git is infrastructure in this codebase in the same way the filesystem
is.

The decision is therefore core, with a seam.
The nav-panel tab list becomes data-driven rather than hardcoded markup, which is the
piece a future `registerNavPanel` SDK surface would build on.
That surface is not designed or shipped here; committing to a contract with only one
consumer would be premature.

### Why the git CLI and not a library

No new dependency. `watch_backends.py` and `cli/remote.py` already shell out, and the
required data comes out of two `git` invocations.
Adding `GitPython` or `dulwich` would trigger the 14-day cool-off in
`SUPPLY-CHAIN-SECURITY.md` for no functional gain.
Absence of a usable `git` executable is a normal, reported condition: the Git tab is
hidden, exactly as it is outside a repository.

## Design

### Approach

A new `metabrowser/git/` subpackage owns repository discovery, bounded subprocess
execution, `git log` and `git show` parsing, and the wire model.
A separate route table under `/api/git/` is composed into the application’s route list
rather than appended to the existing endpoints in `server.py`.

The browser gains two modules.
`git_graph.js` is a pure port of the VS Code layout and SVG renderer with no fetching
and no DOM ownership beyond the SVG it returns, which keeps it testable under the
existing Node `vm` shims.
`git_panel.js` owns the tab: fetching, paging, row rendering, selection, hover, and the
commit-detail request.

### Components

**Server**

- `git/repo.py` — repository discovery and identity.
  Resolves the enclosing repository root, the served root’s position inside it, HEAD and
  whether it is detached, and whether a usable `git` executable exists.
  Results are TTL-cached per served root, mirroring the existing gitignore checker
  cache.
- `git/process.py` — the only place that spawns `git`. `asyncio.create_subprocess_exec`
  with a fixed argument vector, never a shell, a wall clock timeout, and a hard cap on
  bytes read from stdout so a pathological repository cannot exhaust memory or block the
  event loop. Non-zero exit and timeout raise a typed error the route layer converts to a
  response; stderr is logged but never returned verbatim, since it can contain absolute
  local paths.
- `git/log.py` — builds the `git log` argument vector and parses its NUL-delimited
  output into commit records.
  Owns the paging cursor and the decoration parsing that turns `%D` into references.
- `git/detail.py` — the per-commit query: full body plus `--numstat` and `--name-status`
  for the changed-file list, with rename and binary handling.
- `git/wire.py` — the TypedDicts below plus `validate_git_commit`,
  `validate_git_log_page`, and `validate_git_commit_detail`, following the pattern and
  the required-key gate sets in `wire_models.py`.
- `git/routes.py` — the `/api/git/` route table, exported as a list and composed into
  `server.ROUTES`.
- `settings.py` — new bounded constants, published to the browser through the existing
  `METABROWSER_SETTINGS` injection so the two planes cannot drift: page size, maximum
  page size, subprocess timeout, output cap, changed-file cap, and the repository-info
  cache TTL.

**Browser**

- `static/git_graph.js` — `computeSwimlanes(commits, priorLanes)` and
  `renderCommitGraph(row)`. Ported from `scmHistory.ts`, with the VS Code color registry
  replaced by design-token references.
  `priorLanes` is what carries lane continuity across a page boundary.
- `static/git_panel.js` — the tab: initial fetch, scroll paging, row rendering, hover
  card, selection, and the commit-detail fetch.
  Keeps a bounded client-side cache of commit details so a hover and a subsequent
  selection do not issue two requests.
- `static/app.js` — the nav-panel registry replacing the hardcoded tab list, plus the
  commit-detail preview renderer.
- `static/styles.css` — `.git-graph-*` rules ported from the `.history-item` proportions
  in `scm.css`, and the new tokens.

**Design tokens**

The five VS Code lane colors are colorblind-safe and are kept as values, but they are
declared once as tokens rather than inlined, per the core styling rule: `--git-lane-1`
through `--git-lane-5` (`#FFB000`, `#DC267F`, `#994F00`, `#40B0A6`, `#B66DFF`), plus
`--git-ref-local`, `--git-ref-remote`, and `--git-ref-tag` for badges, each with a light
and dark value.

### API Changes

Four read-only endpoints, all under `/api/git/`, all returning JSON.

| Route | Purpose |
| --- | --- |
| `GET /api/git/repo` | Repository presence, root, HEAD, and capability. Cheap and cached; the browser calls it once to decide whether to show the tab. |
| `GET /api/git/refs` | All local branches, remote branches, and tags with their target revisions. |
| `GET /api/git/log` | A page of commits. Query: `limit`, `cursor`. |
| `GET /api/git/commit/{revision}` | One commit’s full message, stats, and changed files. Powers both the hover card and the detail view. |

`GET /api/git/repo` is the gate.
When it reports `is_repo: false` — no repository, no `git` executable, or a repository
Metabrowser cannot read — the browser does not render the tab at all, and the other
three endpoints return the same negative envelope rather than an error.

**Wire model.** TypedDicts in `git/wire.py`, snake_case keys, `total=False` for
conditional keys, matching `wire_models.py`:

```python
class GitRef(TypedDict, total=False):
    id: str        # full refname: "refs/heads/main"
    name: str      # short display name: "main"
    kind: Literal["head", "branch", "remote", "tag"]
    revision: str  # full target sha
    remote: str    # conditional: remote name when kind == "remote"

class GitAuthor(TypedDict, total=False):
    name: str
    email: str

class GitCommit(TypedDict, total=False):
    id: str               # full sha
    short_id: str         # abbreviated sha as git renders it
    parent_ids: list[str] # ordered; [0] is the first parent
    author: GitAuthor
    authored_at: float    # epoch seconds
    committed_at: float
    subject: str          # first line of the message
    refs: list[GitRef]    # conditional: decorations at this commit

class GitLogPage(TypedDict, total=False):
    commits: list[GitCommit]
    cursor: str | None    # opaque; None means end of history
    has_more: bool

class GitFileChange(TypedDict, total=False):
    path: str             # served-root-relative when inside the served root
    old_path: str         # conditional: renames and copies
    status: Literal["added", "modified", "deleted", "renamed", "copied", "typechanged"]
    additions: int | None # None for binary files
    deletions: int | None
    binary: bool
    outside_root: bool    # conditional: in the repo but not under the served root

class GitCommitStats(TypedDict, total=False):
    files_changed: int
    additions: int
    deletions: int

class GitCommitDetail(TypedDict, total=False):
    commit: GitCommit
    body: str             # message after the subject line
    stats: GitCommitStats
    files: list[GitFileChange]
    files_truncated: bool

class GitRepoInfo(TypedDict, total=False):
    is_repo: bool
    root: str | None      # repo root relative to the served root, or None if above it
    head: GitHead | None
    reason: str           # conditional: why is_repo is false, for diagnostics
```

Three model decisions worth stating.

**Paths are translated at the boundary.** Git reports repository-root-relative paths.
The served root may be a subdirectory of the repository, so every path in a
`GitFileChange` is rewritten to served-root-relative through the existing safe-path
helpers.
A changed file that lies inside the repository but outside the served root keeps
its repository-relative path and carries `outside_root: true`; the browser renders it as
text rather than a link.
Nothing outside the served root is ever opened.

**The cursor is opaque.** It encodes the last commit of the page.
Paging is implemented with `--skip` against the same ordering rather than a revision
range, so that lane continuity in the browser lines up with the server’s ordering
exactly. Callers do not construct cursors.

**Statistics are not in the log page.** Computing per-commit numstat for a whole page is
the expensive part of every graph implementation.
`GET /api/git/log` runs one `git log`; per-commit stats arrive from
`/api/git/commit/{revision}`, which the browser calls lazily on hover with a debounce
and caches. The hover card and the detail view are the same payload.

### Bounds and failure behavior

Every constraint here exists because the endpoints run on a request path:

- One `git` invocation per request, with a timeout and a stdout byte cap.
- `limit` is clamped to a maximum page size; an out-of-range value is clamped, not
  rejected.
- The changed-file list is capped, with `files_truncated` reporting the cut rather than
  silently shortening.
- The revision path parameter is validated against a strict hex-and-length pattern
  before it reaches an argument vector.
  It is never interpolated into a string, and no revision expression syntax is accepted.
- Errors are caught only where they can be handled, and causes are preserved.
  A repository error is a normal response shape, not a 500.

## Implementation Plan

### Phase 1: Git subpackage and API

- [x] Add `metabrowser/git/` with `process.py`, `repo.py`, `log.py`, `detail.py`,
  `wire.py`, and `routes.py`
- [x] Implement bounded async `git` execution: fixed argv, timeout, stdout cap, typed
  errors, no stderr passthrough
- [x] Implement repository discovery and the TTL-cached `GitRepoInfo`. Discovery asks
  `git rev-parse --show-toplevel` rather than reusing the `.git` marker search in
  `tree.py`: the marker test accepts directories git itself refuses (a broken linked
  worktree, a repository owned by another user), and the tab needs “can we read it”
  answered, not just “is something there”
- [x] Implement `git log` parsing, decoration parsing into `GitRef`, and the opaque
  paging cursor
- [x] Implement commit detail: body, changed files, rename and binary handling, path
  translation to served-root-relative, and `outside_root` flagging.
  The planned `--numstat` plus `--name-status` pairing does not work; see the notes
  below
- [x] Add the TypedDicts and runtime validators, and the new bounded constants in
  `settings.py`. Conditional keys use `NotRequired` rather than a blanket `total=False`,
  so required keys are required to the type checker as well as to the validators
- [x] Compose the `/api/git/` route table into `server.ROUTES`
- [x] Tests: unit tests over fixture repositories built in `tmp_path` covering a linear
  history, a merge, an octopus merge, a rename, a binary change, a detached HEAD, a
  served root below the repository root, an empty repository with no commits, a
  non-repository root, and a missing `git` executable; wire-shape tests calling the
  validators on every emitted shape; route tests for clamping, the revision pattern
  gate, and the negative envelope

### Phase 2: Git nav panel

- [x] Replace the hardcoded nav tab markup with a data-driven panel registry in
  `app.js`, preserving the current Files behavior including lazy loading and the scroll
  shadow
- [x] Add `git_graph.js`: the swimlane port and the per-row SVG renderer, with lane
  continuity across pages
- [x] Add the lane, badge, and row design tokens, and the `.git-graph-*` rules ported
  from the `.history-item` proportions
- [x] Add `git_panel.js`: gated tab visibility from `/api/git/repo`, initial page,
  scroll paging, reference badges, hover card with debounce and a bounded detail cache,
  and row selection
- [x] Add the commit-detail preview renderer, with changed-file rows navigating through
  `openPath` and `outside_root` rows rendered inert
- [x] Tests: Node `vm` unit tests for the swimlane algorithm against known histories
  including merges and cross-page continuity; SVG structure tests for the renderer; DOM
  tests for tab gating, paging, selection, and hover; an integration test driving a
  fixture repository end to end from `/api/git/repo` through commit detail

## Implementation Notes

Four things surfaced during implementation that the plan did not anticipate.

**Git writes a newline between the format record and the first diff entry.** With `-z`,
`git show --format=… --raw --numstat` terminates the format record with NUL and *then*
emits `\n` before the first `:100644 …` entry.
The first token of the diff section therefore arrives as `"\n:100644 …"`, the raw-prefix
test misses, the walk falls one entry out of step, and the first changed file of every
commit silently vanishes.
This was caught by running against a real fixture repository, not by reading the docs;
`test_commit_detail_lists_every_changed_file` is the regression guard.

**`--numstat` and `--name-status` do not combine.** Git treats them as competing output
formats and the last one given wins, so the plan’s “merge the two sections” would have
produced statuses and no counts.
`--raw` and `--numstat` do emit both sections, and `--raw` additionally carries the
rename similarity score, so the commit endpoint still costs one invocation rather than
the two the plan was prepared to accept.

**Merges need `--diff-merges=first-parent`.** Git’s default for a merge commit is a
combined diff, which shows only hunks that differ from every parent and so reports
essentially nothing for an ordinary merge.
Without the flag, every merge row in the graph opens onto an empty changed-file list.

**Upstream’s HEAD marker passes its circle arguments transposed.** `scmHistory.ts` calls
`drawCircle(circleIndex, CIRCLE_STROKE_WIDTH, CIRCLE_RADIUS)` where the signature is
`(index, radius, strokeWidth)`. It reads like a bug, but it is what produces the filled
dot inside the HEAD ring, so the port preserves the call exactly and explains it at the
site rather than “correcting” it into a different shape.

## Deviations From the Plan

- `git/exec.py` is `git/process.py`. `exec` shadows a builtin, and
  `from metabrowser.git import exec` reads badly at every call site.
- Repository discovery asks git rather than reusing `tree._find_git_root`; see the Phase
  1 task list.
- `.git-file-path` and the per-file line counts do not use the monospace face.
  The chrome-typography rule in `tests/test_chrome_typography.py` is right that a path
  column carries the navigation face, and tabular figures give the counts the alignment
  monospace would otherwise have been reached for.
  Only `.git-commit-sha` and `.git-commit-body` are monospace, both as named exceptions
  in that test.
- `app.js` gained a narrow `window.MetabrowserShell` bridge (`registerNavPanel`,
  `removeNavPanel`, `activateNavPanel`, `renderPreviewHtml`) so `git_panel.js` could
  live outside `app.js`. This is an internal seam between the shell and core modules,
  deliberately separate from `window.metabrowser`, which is the documented plugin SDK
  and carries a compatibility contract.

## Testing Strategy

The swimlane algorithm is the part most likely to be subtly wrong and the easiest to
test, since it is pure.
It is tested directly against hand-written parent lists — linear history, a simple
merge, an octopus merge, a branch that ends mid-page, and a history split across two
pages to prove continuity — asserting lane assignment rather than pixels.

The SVG renderer is tested on structure: node count, lane count, and the presence of
curve paths for merges, not on exact path strings.

The server side is tested against real repositories built with `git` in `tmp_path`, so
the parsers face actual output rather than a fixture that can drift.
Every emitted shape passes through the runtime validators, matching how
`test_browser_wire_shape.py` guards the tree contract.
Failure paths get equal weight: no repository, no `git`, an empty repository, a bad
revision, a timeout, and an oversized output are all asserted to produce the documented
response rather than an exception.

The end-to-end test drives the real application lifespan and route stack against a
fixture repository, which is the pattern the existing integration tests use.

`make verify` is the handoff gate.

## Addendum: Repository-Root Scope (2026-08-09)

The Git feature is enabled only when the served root resolves to the exact working-tree
root reported by `git rev-parse --show-toplevel`. This rule supersedes the plan’s
earlier support for serving a repository subdirectory and rendering outside-root files
as inert rows.

Git history and commit details describe the entire working tree.
Enabling them for a served subdirectory would expose commits and file names outside the
tree Metabrowser can navigate, while filtering those files would misrepresent each
commit. `GET /api/git/repo` therefore returns `is_repo: false` with
`reason: "not_repo_root"` for a served subdirectory, and every other Git endpoint
returns the same negative envelope.
The browser consequently does not register the Git tab.

Linked worktrees remain supported because `--show-toplevel` reports the root of the
current linked worktree, not the primary worktree.
Tests cover a repository root, a linked-worktree root, a repository subdirectory, a
plain directory, and the negative envelope across every Git endpoint.

## Addendum: v0.3.0 Merge and Second Review Round (2026-08-11)

The branch merged the v0.3.0 filtering and server-reliability work.
Three textual conflicts were additive collisions resolved by keeping both sides.
The one that was not mechanical is the `git check-ignore` cross-validation test: both
branches had independently isolated the git environment, and the release branch’s
`_isolated_git_env()` asks git for the authoritative variable list via
`git rev-parse --local-env-vars`, which supersedes this branch’s hardcoded scrub.
The hardcoded tuple stays in `git/process.py`, because the server’s git spawner cannot
shell out to discover the list on every spawn.

The merge also brought a role-based control family (`.btn`, `.icon-btn`) that the Git
panel predates. `.git-panel-refresh` was a hand-rolled near-duplicate that had no
`:focus-visible` ring, so adopting the primitive both removes the duplication and
restores the focus affordance.

A second review round found four further defects, all now fixed:

- **Reopening the tab did not re-read HEAD.** HEAD is an input to lane layout and is
  baked into each row when the page is laid out, so a checkout made while another tab
  was showing can only be recomputed, never repainted.
  The panel now re-reads repository identity on every activation — the response is
  TTL-cached server-side, so a tab switch that changes nothing costs nothing — and
  recomputes when the revision moved.
- **Refresh kept a stale commit-detail cache.** A commit’s object id is immutable but
  its payload is not: refs move as branches and tags do.
  The cache is now cleared as part of the refresh reset.
- **Page cursors carried an unbounded `--skip`.** Malformed cursors were already
  rejected, but a well-formed one could name any offset, and `git log --skip` walks and
  discards the whole prefix.
  `GIT_LOG_MAX_SKIP` bounds it at roughly four hundred pages of the default limit, far
  past anything the panel can reach given its own row cap.
- **The HEAD ring showed a filled disc when selected.** The hollow marker follows the
  row background, but only the default and hover cases had rules.
  The selected rule is ordered after the hover rule because the two carry equal
  specificity, which is what makes source order decide a row that is both; a structural
  test pins that ordering so a future reshuffle cannot silently invert it.

What remains is the manual pass the branch has always been waiting on: a human eye on
the graph’s proportions across themes and the paging boundary.
Everything else is automated-green under `make verify`.

## Attribution

`git_graph.js` is a derivative of `scmHistory.ts` from `microsoft/vscode`, MIT-licensed,
and the row proportions derive from `media/scm.css` in the same repository.
Metabrowser is AGPL-3.0-or-later, which permits incorporating MIT-licensed source.
The ported files carry a header naming the upstream file and its license, and the MIT
notice is retained where required.

The port was copied at upstream commit `9245212c26af8113b3b96392c04563623cd99811`
(2026-08-07), recorded in the `git_graph.js` header and in `NOTICE.md`. That commit id
is the whole provenance record.
There is deliberately no automated check on the license text or the ported source: a
pinned digest next to the file it validates defends against nothing, and would fail on a
trailing newline while catching nothing a reader would not.
The wheel is checked for the presence of `vendor/licenses/vscode.txt`, because shipping
it is a redistribution obligation; its contents are reviewed by a person, once, when
they change.

## Re-syncing with upstream

Pulling in later upstream changes is a manual review, not an automated merge.
The port is deliberately faithful precisely so this diff is readable.

The reference checkout lives in `attic/`, which is git-ignored, so recreate it as
needed:

```shell
git clone --filter=blob:none --sparse https://github.com/microsoft/vscode attic/vscode
git -C attic/vscode sparse-checkout set src/vs/workbench/contrib/scm/browser
```

Then diff the ported file against the recorded commit:

```shell
git -C attic/vscode log --oneline 9245212c26af8113b3b96392c04563623cd99811..HEAD \
  -- src/vs/workbench/contrib/scm/browser/scmHistory.ts
git -C attic/vscode diff 9245212c26af8113b3b96392c04563623cd99811..HEAD \
  -- src/vs/workbench/contrib/scm/browser/scmHistory.ts
```

If that diff is empty, there is nothing to do.
If it is not, review each hunk against `git_graph.js` by hand.
The four intentional divergences are numbered in the file header and each is marked at
its site, so a hunk landing on one of them is a decision, not a mechanical apply.
Re-check `media/scm.css` the same way if row proportions changed upstream.

When the port is updated: refresh the commit id in the `git_graph.js` header and in
`NOTICE.md`, re-copy `vendor/licenses/vscode.txt` if upstream’s license changed, and
note what moved in this spec.
The lane-assignment suite in `tests/dom/git_graph_behavior.js` is what catches a bad
apply, so run it before and after.

## References

- [Architecture](../../../architecture.md)
- [Plugin authoring](../../../plugins.md)
- [Design system](../../../design-system.md)
- [Quick file finder and search providers](plan-2026-07-17-scalable-file-search.md)
- [VS Code graph layout and renderer](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/scm/browser/scmHistory.ts)
- [VS Code source control styles](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/scm/browser/media/scm.css)
- [VS Code git history provider](https://github.com/microsoft/vscode/blob/main/extensions/git/src/historyProvider.ts)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
