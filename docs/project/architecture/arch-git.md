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
| `git/file_ages.py`, `git/file_ages_service.py` | When each file of a revision last changed, from `git last-modified`, and the answers kept per commit |
| `git/shallow.py` | What a shallow boundary leaves certain |
| `git/change_size.py` | A change’s size as Git pushes it and as a patch, measured once and kept |
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
A store target’s `GitLocation` also sets `format.pretty=medium`
(`GIT_NO_CONFIGURED_FORMAT_ARGS`), since that setting can hold `%G?`, which verifies a
signature for a `show` or `log` without a format of its own, and `core.fsmonitor=false`
with `core.hooksPath` at the null device (`GIT_NO_HOOK_ARGS`), since a read of an index
path runs the one and a ref written runs a hook.
A store target that names no policy gets the store policy, and a store spawn is refused
when its policy would allow lazy fetch, or when its arguments have a shape that would
start a program the repository’s configuration names (`_require_no_configured_program`):
a `diff`, `show`, or `log` without the driver options after its command and the
signature, submodule, and format settings before it; another value for one of those
settings or the hook settings; `--show-signature`, `--textconv`, `--ext-diff`,
`--alternate-refs`, a signature in a format or a sort, or a format given by name; a
`cat-file` or `hash-object` filter, an editor, or a `rev-list` content search; and,
under the read policies, any command outside `_STORE_READ_COMMANDS` and a `symbolic-ref`
or `config` that writes.
The guard reads arguments only: it does not see what a batch reads from its input, or an
index path, which only a read through a `GitLocation` is protected for.

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
`git/wire.py`. Every address and copy carries the full ID. Git’s own abbreviation comes
as `short_id`, which respects `core.abbrev` and grows with the repository, for a caller
that hands it back to Git; the page shows a commit by a fixed length cut from `id`, as
GitHub does ([Short Commit IDs](../../design-system.md#short-commit-ids)), since a shown
ID is read, not resolved.

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
commit by default rather than the store’s `HEAD`. Every route of the Commits tab reads
the served pin as that commit (`session_git_location` in `git/routes.py`), a mirror’s
and a checkout’s alike, so the tab shows the revision the Files tab shows.

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
| `/api/git/commit-markdown/{revision}` | One commit’s body rendered as Markdown, with its trailers as written |
| `/api/git/commit-size/{revision}` | One commit’s size as Git pushes it and as a patch |

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

`/api/git/commit-markdown/{revision}` reads the commit’s message with one `git show -s`
and renders its body through the path a pull request’s description takes: KPress in the
Markdown child under its deadline, then the inert allowlist.
The commit page asks for it beside the commit route, which keeps the message as written
for the hover card and for a body that is not rendered.
The `git/message.py` docstring says what differs from a description: Git’s trailers are
split off as written, links resolve against `COMMIT_MESSAGE_LINK_BASE`, so only an
absolute one keeps its address, and a body past `GIT_COMMIT_BODY_MARKDOWN_MAX_BYTES`
(`settings.py`) answers 422 `body_too_large` and is shown as written.
The same 404 and 400 answers apply, and a revision that names an object that is not a
commit is not found.

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

A link to a commit elsewhere on the page reads the commit through the same cache, by
public methods of `window.MetabrowserGitPanel` that the link card’s provider
(`static/link-preview-providers.js`) calls.
`commitSummary(revision)` answers the subject, author, and commit time from the cache, a
read already on its way, or one more read the panel then keeps, and answers a commit the
server called `commit_not_found` missing without asking again until the panel’s Refresh
or a fetch clears that answer; it reads only a full commit ID and never fetches from
origin. `keptCommitSummary(revision)` answers the same from what the panel holds now,
with no read, for the card the pointer’s arrival shows, so the card keeps nothing of its
own and says what the panel’s cache says.
`prefetchCommit(revision)` prepares the commit as a hover on its row does, and prepares
nothing for a commit the repository lacks or in place of a preparation still on its way,
so a rest on a link aborts no request.

## File Ages

**Status:** Implemented: a pinned revision’s tree nodes and file envelopes carry
`mtime`, its index progress carries the state of getting it, Group by age, Modified
within, and Recent read those times, and the page draws again when they land.

A Git revision has no modification times, so a file’s age is the committer time of the
last commit that changed it, which is what a hosting site’s file list shows, and a
directory’s is the newest of its files’.
`git/file_ages.py` takes both from Git itself: it runs
`git last-modified -r -z <commit>` at the store, reads the commit each file names, asks
`git log --no-walk` for those commits’ times, and walks no history of its own.
The meaning is `git log -1 -- <path>`’s, which history simplification gives: a change on
a side branch that a merge discarded is not the file’s last change, and a file only a
merge’s resolution changed is dated by the merge.
A plain `git log --name-only` pass gets both wrong, which is why this does not stand in
for the command.

- **The Git it needs.** `git last-modified` is Git 2.52’s and experimental there.
  `FILE_AGES_GIT_MINIMUM` is the first release that carries the fixes of its early
  defects, and it is tested at the release the `admitted-git` CI job builds for it, not
  at the minimum itself.
  The read names neither a pathspec nor a subdirectory.
  With an older Git, or when the command fails, nothing replaces it: a revision shows no
  times, as before, `/api/capabilities` says so (`file_ages.hint`), and `metab --doctor`
  names the version found and the step that upgrades it.
  `file_ages_availability` is the one place the question is answered.
- **Never waited for.** `file_ages_service.FileAgesService` keeps one answer per commit
  ID, in memory, bounded by `GIT_AGES_CACHE_REVISIONS`, and reads a missing one as a
  background job named `file_ages.read` in the [event log](../../realtime-debugging.md).
  A route asks `request`, which returns the answer, or `dating`, or why there is none,
  at once. `/api/tree` carries `mtime` on the nodes it can date and an `ages` state;
  `/api/index/progress` carries the same state, which a page polls and a command that
  prints it waits on (`wait_for_index` in `cli/asgi_client.py`, for `/api/tree`,
  `/api/recent` and the progress route itself, and for `/api/file` only when asked with
  `?ages=1`, which the route ignores: a file’s envelope takes its time from an answer
  that is there and starts no read, since a page opens many files and asks for none.
  Every other `--api` route passes `ages=0` and never starts the read).
  A file the answer leaves undated carries no `mtime`. A read that fails is asked again
  after `GIT_AGES_RETRY_AFTER_S`, and every step of one is inside its `file_ages.read`
  span, so a failure leaves a record with Git’s stderr.
  An answer cut by its budget is served, and the first request after
  `GIT_AGES_CUT_RETRY_AFTER_S` starts a read to replace it while it goes on being
  served, so a history too large to finish does not lose its ages for the length of
  every read; a read that fails leaves it.
  At most `GIT_AGES_MAX_CONCURRENT_READS` reads run at once across every revision the
  process shows, because a read’s memory follows its history; the next waits for a slot
  and is `dating` meanwhile, and a read cancelled while it waits leaves the queue.
  A served pin has one revision and leaving it cancels its read, so the bound is a
  defence for a caller of the service, and only its tests reach it.
- **What reads them.** The age bands and windows are cut at one instant per request, so
  the groups of one grouped answer partition the times; a file the answer leaves undated
  is in no window and no band but a last group, `undated`, whose name carries
  `older_than` when the answer has one.
  A grouped answer asks for the state of the read once and buckets every file once at
  that instant (`_GitTimes`), so all its groups are cut from one state of one answer,
  and the split costs one pass over the files and not one per group (the measurement is
  beside `_GitTimes`). The answer carries `recency_tallies` for the Modified within
  menu, grouped or not.
  A folder row in a group or a window is dated by the newest of the files that put it
  there, as its count is, and not by the whole folder.
  A submodule (a gitlink) has no time and is no file the answer dates, so it is listed
  in no age group and in no window, as it is in the ungrouped tree and in By file type.
  `/api/recent` lists the newest files of a window with the folders above each by name
  (`dir_names`) and counts the files it could not date (`undated`): those that pass its
  other filters and have no time, whatever the window, since a window cannot place them
  and a shallow clone’s may be inside it.
  The file envelope carries `mtime` only from an answer that is already there.
  OLD

swap(<<'OLD', <<'NEW', “the page”);
- **The page.** A response that says `ages.state` is `dating` starts one watch
  (`static/revision-ages.js`) that asks `/api/index/progress` every `GIT_AGES_POLL_MS`
  and, when the answer lands, draws the tree, grouped tree, or Recent list again, once;
  folders opened before it are read again when opened.
  The page never waits: until then every file is undated.
  OLD
- **The page.** A response that says `ages.state` is anything but `ready` brings in
  `static/revision-ages.js`, an on-demand script (the `revision-ages` bundle, offered
  only to a page whose Git can read ages), so a page whose Git cannot, or whose answer
  was whole at its first request, never fetches it.
  A `dating` response starts one watch that asks `/api/index/progress` every
  `GIT_AGES_POLL_MS`, retries a failed poll a few times, and gives up after
  `GIT_AGES_WATCH_GIVE_UP_MS`. When the answer lands, or a response says it has, the
  page draws the tree, grouped tree, Recent list and the open file again, once, and
  drops the folders it had read.
  The page never waits: until then every file is undated, the Modified within counts
  read “…”, a Recent list says it is reading, and the line that counts the files a
  filter keeps adds a clause saying so (an item of a line that is already there, so the
  tree does not move; `annotate`); it also says why a read failed and how many files
  could not be dated, and the Undated group’s name says which state it is in.
  A revision whose Git cannot date its files has `recency` false, so these answer
  `unsupported_for_subject` and the page does not offer them
  (`GitRevisionSubject.capabilities`, `METABROWSER_FILE_AGES`).
- **The page.** A response that says `ages.state` is `dating` starts one watch
  (`static/revision-ages.js`) that asks `/api/index/progress` every `GIT_AGES_POLL_MS`
  and, when the answer lands, draws the tree, grouped tree, or Recent list again, once;
  folders opened before it are read again when opened.
  The page never waits: until then every file is undated.
- **Per commit.** A commit ID names a tree for good, so an answer is never stale: a
  branch shown again is a lookup, a new branch or tag is read for its own tip, and a tip
  whose ancestor is answered, with no merge commit between them, reads `C ^A`, so Git
  walks only the commits since it.
  That derivation is the same answer as a cold read only over a range with no merge:
  Git’s `^A` boundary marks a file whose last change it could not place after `A`, and
  across a merge that can name `A` for a file whose last change is older (a merge that
  restores a mode, for one).
  `nearest_ancestor` therefore offers an ancestor only when
  `git rev-list --merges --count A..C` is 0, and never an answer that was cut by its
  budget, and otherwise the answer is read cold.
  A file the derived read reports as unchanged since an excluded commit other than the
  ancestor would need that commit’s own answer, so the whole answer is then read again,
  with its own budget.
  `tests/test_git_file_ages.py` checks cold reads against `git log -1 -- <path>`, and
  derived reads against cold ones over random histories with merges.
- **What it does not know.** A shallow boundary is a root to Git, which adds every file,
  so a file last changed there is *undated* and the answer says `older_than`: the
  boundary commit’s time, never the time a file was not changed at.
  A read past `GIT_AGES_TIMEOUT_S` is cut, and Git prints a file as soon as it knows it,
  so the files it had printed keep their times and the rest are undated, last changed
  before the oldest commit printed.
- **A checkout’s revision.** The mechanism is the same: the commit’s store target is the
  checkout’s Git directory, which a read leaves as it found it, and the answers are in
  the process’s memory, so nothing is written there.

`settings.py` records beside `GIT_AGES_TIMEOUT_S` what a read cost on four histories,
with and without a commit-graph, and what a one-level read cost, which is why no store
is given a commit-graph and why the whole tree is read, not the directory on screen.

## Change Sizes

A change’s size is two numbers, both measured by `git/change_size.py`: the thin pack
`git push` sends for it, every object the head reaches that the base does not,
compressed and stored as deltas against each other and against the base’s objects
(`pushed_bytes`), and its patch, `git diff --binary`, uncompressed (`diff_bytes`), with
the commits the change holds.
A commit’s change is against its first parent, as its detail is; a pull request’s is its
head against the merge base its Files changed compares.
Neither the sum of the new objects’ sizes nor their size on disk answers the question:
the first counts every touched file and directory whole, and the second depends on how
the repository’s packs happen to be laid out; the module docstring has the measurements.

Every option that could move either number is pinned on the command line, the reader’s
and the repository’s configuration included, and `--no-reuse-object` keeps the store’s
own packs out of the pack, so a size is a function of the two commit IDs and of the zlib
Git is built with. A measured size is therefore never measured again: it is kept in
memory, and for a [repository store](arch-repository-cache.md#layout) in its
`change-sizes/` bank, which a fresh server reads.
A served folder keeps sizes in memory only, since browsing a folder never touches the
cache. `pack-objects` is a store read only with `--stdout`, which `git/process.py`
enforces.

What cannot be known is answered `unknown` with a reason, never as a number that is
wrong: `parent_unavailable` at a shallow boundary, `history_unavailable` for a walk that
crosses one, `objects_unavailable` for an object the repository lacks, and `too_costly`
past the request deadline, which is kept for the process so it is paid once.
`/api/git/commit-size/{revision}` is a route of its own, apart from the commit route the
hover card asks for on every row, because a first measurement takes a pack’s time.
The pull request’s size is `GET github/pull-size`
([GitHub Pull Requests](arch-github-pull-requests.md)).

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
`GitChangeSize` is a `TypedDict` because it is a field of `TypedDict` answers, the Pulls
rows’ summary among them, and its validator, `validate_git_change_size`, is its one
gate.

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
