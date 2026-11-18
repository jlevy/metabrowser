# Git Reading and History

**Status:** Implemented: the process boundary, repository discovery, the `/api/git/`
routes, history sessions with graph checkpoints, the browser’s history window, and
commit detail, for a served folder and for a pinned revision.
Planned: working-tree status and diffs, in the
[Git status plan](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md).

Metabrowser reads Git and never writes a repository it serves;
[Known Gaps in the Read-Only Rule](#known-gaps-in-the-read-only-rule) names the two
reads where Git itself does.
This document covers how it starts Git, what the Commits panel asks of it, and how the
answers stay bounded.
[Source Sessions and Pins](arch-source-sessions-and-pins.md) covers what a session
serves and how a pinned revision projects its tree, and the
[Diff Pipeline](arch-diff-pipeline.md) covers comparisons.

## Modules

| Module | Role |
| --- | --- |
| `git/process.py` | Starts every `git` process the server and acquisition run |
| `git/repo.py` | Repository discovery and the exact-root gate |
| `git/routes.py` | The `/api/git/` route table |
| `git/log.py`, `git/detail.py` | Argument vectors and parsers for refs, log records, and one commit |
| `git/history.py` | History sessions, cursors, and graph checkpoints |
| `git/ref_state.py`, `git/route_memo.py` | Naming the refs’ state, and answers kept under it |
| `git/shallow.py` | What a shallow boundary leaves certain |
| `git/wire.py` | The JSON shapes the routes emit, and their validators |
| `static/git-graph.js` | Lane assignment and row SVG, ported from VS Code |
| `static/git-history-window.js` | The browser’s page cache and virtual window |
| `static/git-panel.js` | The Commits panel: requests, DOM, selection, and commit detail |

## The Process Boundary

`git/process.py` creates every Git process that serving, reading a store, and
acquisition need, so the properties below hold for all of them and a new Git feature
extends that module rather than adding a second wrapper.
It has two seams:

- **`run_git`** runs a command to completion and returns its bounded stdout.
  Every request-scoped read uses it.
  Given `stop_when`, it stops Git once Git has printed what the caller can use.
- **`spawn_git_process`** returns a live process whose streams the caller owns, for a
  consumer that cannot wait, such as a history walk read page by page.
  It shares the executable lookup, environment, fixed arguments, and spawn-failure
  translation, so the guarantees are the same.
  Its caller also owns ending the process with `terminate_git_process`.

`run_git_at` and `spawn_git_at` take a `GitLocation`, which names either a worktree path
or a trusted store target, never both.
Each spawn runs under a named `GitProcessPolicy`: `READ_POLICY` for a served folder,
`STORE_READ_POLICY` and `BATCH_OBJECT_POLICY` for a Metabrowser-owned store, and
`ACQUISITION_POLICY` for fetching.
A revision a folder’s server shows of its own checkout is read as a store is: its target
is the checkout’s Git directory, with no worktree, under the two store policies
([Revisions of a Checkout](arch-source-sessions-and-pins.md#revisions-of-a-checkout)).
Every `diff` and `show` at a store target also says `--no-textconv --no-ext-diff`
(`GitLocation.diff_driver_args`), since those policies leave a repository’s local
configuration in effect and a checkout’s can name a driver.
Every command run at a `GitLocation`, a served folder’s included, sets
`log.showSignature=false` (`GIT_NO_SIGNATURE_ARGS` in `GitLocation.config_args`): with
that setting on in a repository’s configuration, `log` and `show` verify signatures by
running the program `gpg.program`, `gpg.ssh.program`, or `gpg.x509.program` names, and
no page shows a signature’s state.
Every command at a store target also sets `diff.submodule=short`
(`GIT_NO_SUBMODULE_DIFF_ARGS`): with `diff`, a patch diffs each changed submodule in a
child Git in the submodule’s own Git directory, which runs that directory’s drivers
whatever the parent passes.
A store target that names no policy gets the store policy, and a store spawn is refused
when its policy would allow lazy fetch, or when it could run a program the repository’s
configuration names (`_require_no_configured_program`): a `diff`, `show`, or `log`
without the driver options after its command and the signature and submodule settings
before it, a setting or option that turns either back on, a signature in a format, a
`cat-file` or `hash-object` filter, an editor, a `rev-list` content search, and, under
the read policies, any command outside `_STORE_READ_COMMANDS`.

| Invariant | Mechanism | What it prevents |
| --- | --- | --- |
| No shell | `create_subprocess_exec` with a fixed argument vector | A path or URL becoming a command |
| No ambient repository | `_REPO_PINNING_GIT_VARS` are removed from every child’s environment | Reading another repository than the one addressed, as a Git hook’s exported `GIT_DIR` would |
| No lock contention | `--no-optional-locks` and `GIT_OPTIONAL_LOCKS=0` | A browser read blocking a terminal Git command, or writing the index |
| No hanging prompt | `GIT_TERMINAL_PROMPT=0` and empty `GIT_ASKPASS` and `SSH_ASKPASS` | A credential prompt stalling a request |
| Bounded output | Incremental reads capped at the policy’s `max_bytes` | An unbounded buffer from a hostile or huge repository |
| Bounded time | The policy’s deadline, then terminate and reap | A wedged process outliving its request |
| Early stop | `stop_when` sees each stdout read; once it says enough, terminate, then kill after a grace period, and `GitOutputCutError` carries what was printed | Git printing output its caller would throw away, such as a comparison’s patch past `MAX_LISTED_PATCH_BYTES` |
| Counted spawns | Each successful spawn calls `server_timing.git_process_started()` | A request’s Git cost hidden from `Server-Timing`, whose `git` entry counts the processes it started |
| No deadlock | stdout and stderr drained concurrently | Both pipes filling while one is unread |
| No leaked paths | stderr is capped and only logged, through `loggable` | Absolute local paths reaching a response, or escape sequences reaching a terminal |

An isolated policy also removes every inherited `GIT_*` variable and ignores the
reader’s Git configuration and attributes; `process.py` says why for each.
The bounds are `GIT_SUBPROCESS_TIMEOUT_S` and `GIT_SUBPROCESS_MAX_BYTES` in
`settings.py`, and `GIT_ACQUISITION_TIMEOUT_S` in `process.py`.

Failures are typed under `GitError`: `GitUnavailableError`, `GitCommandError`,
`GitTimeoutError`, `GitOutputTooLargeError` (with `GitOutputCutError` under it for a run
stopped early), and `UnsupportedGitVersionError` for acquisition’s version floor.
Callers branch on the type, so “Git is not installed” stays apart from “the command
failed”. `GitError` is a `ContentReadError`, so a plugin hook reading a pinned blob
catches one family for both kinds of source.

`run_git` returns bytes.
Git emits paths in whatever bytes the filesystem holds, and the parsers’ record
separators are bytes, so each parser decodes at its own granularity.

`GIT_OPTIONAL_LOCKS=0` makes reads observational: a plain `git status` rewrites
`.git/index` to persist its stat cache, and with optional locks off it does not.
The cost is that the stat cache never persists, so a feature that polls Git pays a cost
that does not amortize.

### Known Gaps in the Read-Only Rule

`READ_POLICY`, which a served folder’s own Git reads run under, keeps the reader’s and
the checkout’s Git configuration and sets no lazy-fetch guard.
Git therefore writes into the checkout’s Git directory in two cases:

- **A partial clone.** A read that needs a blob the clone lacks makes Git fetch it from
  the promisor remote and store a new pack.
  Commit detail’s `git show --numstat` is such a read.
  The store policies set `GIT_NO_LAZY_FETCH=1`, under which the same read fails and
  fetches nothing.
- **A cached textconv driver.** Where the checkout’s configuration names a textconv
  driver with `cachetextconv`, a comparison that runs the driver makes Git write
  `refs/notes/textconv/<driver>`.

Both were reproduced on 2026-11-18 with Git 2.50.1, through `/api/git/commit/<rev>` on a
`--filter=blob:none` clone and through `/api/plugin/diff/comparison` on a checkout with
such a driver. No test holds either yet (`mb-z849`). A third case is closed for every
location: a signature program named by the checkout’s configuration, which
`log.showSignature` would run from the Commits tab, is never started, and
`tests/test_checkout_revisions.py` holds that for a folder’s own history as for a
revision’s. [Open Modes](arch-open-modes.md#what-is-never-written) states the rule they
fall short of, and requires that a revision of a checkout never reach either.

### The One Other Git Process

`build_version.py` also runs `git`, with `subprocess.run`, to annotate the version line
of a source checkout with its distance from the last tag, its commit, and whether it is
dirty.
It runs only when the running package is Metabrowser’s own tracked source, at most
once per process (`build_state` is cached), under its own timeout and with every `GIT_*`
variable removed, and any failure falls back to the plain version.
It never reads a served repository.
`tests/test_git_arch_doc.py` fails the build if any module other than `git/process.py`
and `build_version.py` both starts a process and names `git`. That is a text scan, so it
catches a new spawn site and not a process started through an indirection it cannot see.

## Paths and Object IDs

A POSIX path is bytes, excluding NUL and `/`, and need not be UTF-8. Across the Git and
diff layers:

- Identity, sort order, and comparison use raw bytes.
- Display is a lossy projection: `path` for UTF-8 display, plus `path_b64` with the
  exact bytes when the two differ.
- HTML and URL output always escape the display string.

Line-oriented commands run with `core.quotepath=false`, so Git emits UTF-8 instead of
octal escapes. Commands that must carry any byte use `-z` NUL framing, where Git does no
quoting at all.

Object IDs are full: SHA-1 or SHA-256 hexadecimal, checked by `is_full_revision` in
`git/wire.py`. Abbreviations come from Git as `short_id`, which respects `core.abbrev`
and grows with the repository; truncating in the browser would eventually collide.

## Discovery and the Exact-Root Gate

`git/repo.py` asks `git rev-parse --show-toplevel` and compares the answer to the served
root. A served folder is Git-capable only when the two are equal.
History spans the whole repository, so serving a subdirectory as a Git root would let
the Commits panel describe files outside the tree the user chose to browse; widening the
gate is a containment change.

[Open Modes](arch-open-modes.md#resolving-a-target-to-a-root) designs opening a path
inside a repository at the repository’s root.
The gate then stays as it is, and refuses only a folder served exactly, below a
repository’s root.

Discovery answers a negative reason, such as `not_repo_root`, and never raises to a
route. Linked worktrees qualify because Git reports each worktree’s own root.
Anything that reads per-worktree control files resolves them through Git rather than
assuming a `.git` directory.

A pinned revision is not a working tree.
Its `GitLocation` is a `RepositoryStoreTarget` plus the pinned commit ID; discovery
reports a detached `HEAD` at that commit and an empty `root`, and history walks that
commit by default rather than the store’s `HEAD`.

The identity is cached per location for `GIT_REPO_INFO_TTL_S`. Past it, a repository the
reader owns keeps its identity while the refs’ state (below) is unchanged, and
rediscovers in the background once it is `GIT_REPO_INFO_MAX_AGE_S` old; the module
docstring says what each case covers.
`tests/test_git_repo_identity.py` holds it.

## The Collection API

The read-only routes, registered as `GIT_ROUTES` in `git/routes.py`:

| Route | Serves |
| --- | --- |
| `/api/git/repo` | Repository presence and `HEAD`; the gate for everything else |
| `/api/git/refs` | Branches, remote branches, and tags |
| `/api/git/summary` | History depth for the panel header: commit count in scope and oldest root-commit date |
| `/api/git/log` | One page of a history session |
| `/api/git/commit/{revision}` | One commit’s message, files, and counts |

`tests/test_git_arch_doc.py` compares this table to `GIT_ROUTES`. The routes also appear
in the [views, models, and routes map](arch-views-models-routes.md).

The rules in the `git/routes.py` docstring hold across them:

- **`/api/git/repo` is the gate.** When it says `is_repo: false` the browser does not
  render the Commits tab, and every other route answers the same negative envelope with
  HTTP 200, because “not a repository” is an ordinary state and a 4xx would send it down
  the browser’s error path.
- **Revisions are validated before they reach an argument vector.** Only a full object
  ID passes, so a caller’s value cannot be read as an option or a revision expression.
- **Numeric parameters are clamped, not rejected.**
- **Git failures become a 5xx with a generic body,** 504 for a timeout, because Git’s
  error text names local paths.

`/api/git/summary` walks the whole scope, so the panel asks for it after the first page
paints, as the file tree defers its tally row.

A commit the repository lacks answers HTTP 404 `commit_not_found`, and a short ID or ref
name answers 400 `revision_not_full`. The route never fetches: a GET starts no network
work. On a served mirror the commit view can ask for the fetch such a commit waits for,
`POST /api/source/refresh` with `{"for": "commit"}`; the functional row
`git.unfetched-commit` in the [parity registry](arch-parity-registry.md) pins that
sequence.

## Answers Kept Under the Refs’ State

Refs, summary, and log answer from refs, and resolving a scope takes several Git
processes. `git/ref_state.py` names the refs’ state without running Git, from one `stat`
per file those answers read beyond the object graph; its docstring lists them.
Under one state:

- a history scope is resolved once (`current_history_scope` in `git/history.py`);
- the refs and summary bodies are kept in `git/route_memo.py`;
- a later log page skips proving its scope still holds, and a first page asked for again
  replays the live session that answered it.

Each answer carries an entity tag, and a client holding one this process made is
answered 304. The state does not cover another worktree’s `HEAD`, so the summary counts
the scope the log walks rather than `rev-list --all`. A repository with more ref entries
than `MAX_REF_ENTRIES` gets no state and is answered afresh.
`tests/test_git_route_memo.py` moves every covered input once, with the files backend
and with reftable, from a main and from a linked worktree.

## History Sessions

A page of `git log` output has no object ID: its offset means something only while the
ordered walk that produced it exists.
So the position gets an opaque cursor, and the cursor carries the rules that say when it
stopped being true.

`git/history.py` holds one demand-driven `git log --date-order` walk per session,
started through `spawn_git_at` with the scope’s revisions on stdin.
Date order shows no parent before its children, which is what makes one page’s ending
lane state the next page’s starting state.
Pages already read are framed into a private spool and replayed by indexed seek, so
revisiting a page reads a file rather than walking again.

The cursor is base64 JSON with a format version, the session ID, the scope fingerprint,
the direction (`d`), the page number, and the page size.
`decode_history_cursor` checks the exact key set, the version, bounded IDs, a known
direction, and integers that are not `bool`; every invalid shape decodes to `None`.
`HistorySessionRegistry.read_page` then refuses a cursor whose page size differs from
the request’s own, raising the same `InvalidHistoryCursorError` an invalid shape gets.

Each failure is typed, because each calls for a different recovery:

| Failure | Means | Route answer |
| --- | --- | --- |
| `InvalidHistoryCursorError` | The cursor is malformed or disagrees with the request | 400 `history_cursor_invalid` |
| `StaleHistorySessionError` | The repository or ref scope changed after the session began | 409 `history_stale` |
| `ExpiredHistorySessionError` | The session was idle-reaped, evicted, or shut down | 410 `history_expired` |
| `HistoryStorageError` | The session exhausted its replay-storage budget | 507 `history_storage_exhausted` |
| `HistoryParserError` | A record overran the parser budget, or the spool disagrees with itself | 500, as any `GitError` |

`tests/test_git_arch_doc.py` compares this table to the error classes in
`git/history.py`.

Every resource a session holds has its own bound in `settings.py`, beside the
measurement that set it: `GIT_HISTORY_SESSION_MAX_ENTRIES`,
`GIT_HISTORY_SESSION_MAX_WALKS`, `GIT_HISTORY_SESSION_IDLE_TTL_S`,
`GIT_HISTORY_SESSION_MAX_STORAGE_BYTES`, and `GIT_HISTORY_SESSION_PARSER_MAX_BYTES`,
which a session scales with its page size.
The evidence is in
[the history measurements](../../../explorations/git-history/README.md).
A session’s process, spool, and registry entry are released together on eviction, idle
reaping, and shutdown, and a failed walk discards its session.
Shutdown drains a walk’s output before reaping it, since a walk blocked on a full pipe
never exits.

The rule for anything that holds a Git process across requests: own its whole lifecycle.
Bound the count and the storage, expire on idle, release on shutdown, and give the
client a typed way to learn its handle is gone, so it can recover.
`tests/test_git_history_session.py` covers each bound and failure.

## Graph Checkpoints and Swimlanes

`static/git-graph.js` assigns lanes and draws each row’s SVG. It is a port of VS Code’s
Source Control Graph, with each local change noted in its header.
Lane assignment runs across pages: a page’s first row needs the lanes still open at the
end of the page before it.

The server keeps that state so a page can be drawn without its predecessors.
Each session page carries a `graph_checkpoint`: `prior_swimlanes`, the lanes and colors
open before the page, `color_index`, the palette position, and the head revision and
scope fingerprint they were computed for.
`_advance_graph_checkpoint` in `git/history.py` runs the same lane rules as
`computeSwimlanes` in `git-graph.js` over each page as it is framed, with the same lane
color tokens and the same color for the lane `HEAD` is on, and keeps only the
checkpoint, not row models.
A checkpoint is part of the replayed page, so an evicted page replays with the lanes it
started with.

The browser validates each checkpoint against its page’s fingerprint and head and
refuses a page without one rather than drawing a plausible graph from empty lanes.
It runs `computeSwimlanes` from the checkpoint only over the rows in the virtual window.
Row geometry, path commands, and the SVG stay in the browser.
`tests/test_git_history_session.py` pins the server’s checkpoints, including colors
across a merge, and `tests/dom/git-graph-behavior.js` and
`tests/dom/git-panel-behavior.js` pin the browser’s lanes.

## The History Window

The server owns the unbounded walk; `static/git-history-window.js` owns only the
browser’s working set, with no DOM or network dependency, so its bounds are tested
without a browser:

- **A page cache** of decoded pages, least recently used first, bounded at
  `GIT_HISTORY_PAGE_CACHE_PAGES`.
- **A virtual window** of fixed-height rows that mounts at most
  `GIT_HISTORY_WINDOW_MAX_ROWS`, with `GIT_HISTORY_WINDOW_OVERSCAN_ROWS` on each side.
- **A physical scroll segment** that rebases before `GIT_HISTORY_SEGMENT_REBASE_PX`, so
  the scroller never approaches the browser’s element-height clamp however deep the
  history. Every `scrollTop` it takes is relative to the first history row, and the panel
  converts.
- **`classifyPageFailure`**, which reads a failed page as `stale` (the refs moved: say
  the history changed and offer a reload), `recover` (the session expired with nothing
  changed: rebuild the walk), or `failed` (retry in place).

These settings reach the page through `window.METABROWSER_SETTINGS`. `git-panel.js`
keeps one replay cursor per visited page, so any visited page can be fetched again in
one request, and asks for the next page `PAGE_AHEAD_PX` before the end.

## Commit Detail

`git/detail.py` reads one commit with a single `git show` carrying `--raw` and
`--numstat`, because each holds half of a changed-file row and a second command would
double the cost of the route the hover card calls.
Merges are diffed against their first parent: Git’s combined diff shows almost nothing
for an ordinary merge.
A commit touching more than `GIT_COMMIT_MAX_FILES` files reports `files_truncated`, and
`stats` still describes the whole commit.
A commit at a shallow boundary, which Git grafts into a root, reports its counts as
unknown rather than a whole tree added; `git/shallow.py` reads its recorded parents.

In the browser the hover card and the commit view share one request and one cache of
`GIT_DETAIL_CACHE_SIZE` entries, and the hover waits `GIT_HOVER_DEBOUNCE_MS` so a drag
across the graph does not ask for every row.
The commit view at `/commit/<rev>` shows the summary, any files outside the served root,
and the commit’s first-parent comparison rendered by the diff plugin’s own view; it has
no diff surface of its own.
The page keeps those comparisons, as [the diff pipeline](arch-diff-pipeline.md#caches)
describes.

## Wire Models

`git/wire.py` uses `TypedDict` with `NotRequired`, plus validators and `_*_REQUIRED`
gate sets that restate the class bodies; the module says to keep them in sync.
The trade is deliberate: producers build plain dicts that go to the wire with no object
construction, which matters for a log page of hundreds of commits.
`diff/format.py` uses frozen Pydantic models with `extra="forbid"` and a `StrEnum` per
closed vocabulary.

For a new Git model, default to the `diff/format.py` idiom.
Use `TypedDict` only where a producer streams many rows and the construction cost is
measured, and then say so in the module and keep the gate set in one place.

## Providers

The GitHub plugin describes hosted state that Git does not model, such as reviews,
checks, and threads, and refers to Git content by object ID. It composes no Git command
of its own: repository selection and pull-request acquisition may ask for explicit refs,
but core resolves them to object IDs, and content, history, and diffs stay Git’s. Git
code does not import provider code.
[GitHub pull requests](arch-github-pull-requests.md) describes the provider.

## References

- [Open Modes](arch-open-modes.md)
- [Source Sessions and Pins](arch-source-sessions-and-pins.md)
- [Diff Pipeline](arch-diff-pipeline.md)
- [Views, models, and routes](arch-views-models-routes.md)
- [Continuous Git history measurements](../../../explorations/git-history/README.md)
- [Git graph view plan](../specs/done/plan-2026-08-06-git-graph-view.md), including how
  to re-sync `git-graph.js` with VS Code
- [Git status and working-tree diffs](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
