# Git and Comparison Sources

**Status:** Implemented for the subprocess boundary, repository discovery, the
`/api/git/` collection API, and the immutable-revision diff source.
The provider layer is designed only; its section says so and links the plan.

How Metabrowser talks to Git, and how anything that produces a comparison plugs into the
one renderer. [File Diff Format v1](file-diff-format/file-diff-format.md) defines what a
comparison document *is*, and
[Diff sources, context, and anchoring](file-diff-format/diff-sources-and-anchoring.md)
covers provenance and anchoring within the diff pipeline.
This document covers the Git side: the process boundary, what crosses it, and the rule a
new source has to satisfy.

## The three layers

The stack has three tiers, and the dependency arrow only ever points down:

```text
┌─────────────────────────────────────────────┐
│ Providers (GitHub)          designed only   │  ← references Git object ids
├─────────────────────────────────────────────┤
│ Git                         implemented     │  ← produces File Diff Format
├─────────────────────────────────────────────┤
│ File Diff Format            implemented     │  ← knows nothing above it
└─────────────────────────────────────────────┘
```

Each tier obeys one rule, and the rules are what keep the tiers separable:

- **File Diff Format is source-neutral.** It has no Git vocabulary.
  A renderer never learns whether a document came from a `.patch` file, a commit, or a
  pull request. No source may add a field to it for its own convenience.
- **Git is a source, not a substrate.** It produces File Diff Format documents through
  the `DiffSource` port and otherwise exposes its own read-only collection API. It does
  not reach into the renderer.
- **Providers layer on Git, never beside it.** Git stays authoritative for content,
  history, and diffs. A provider record describes hosted state and *refers to* immutable
  Git object ids; it never becomes a second copy of the object database.

The practical payoff: a pull-request view resolves provider refs to object ids and
reuses the entire existing pipeline.
It is a new acquisition path, not a new renderer.

## Why identity is the whole problem

Git has exactly one content-addressed object store.
Anything with an object id is immutable, so it can be cached forever and addressed by
that id. Everything in the implemented Git surface — history, commit detail, revision
comparison — lives entirely inside that guarantee, which is why it needs no invalidation
model.

Three things in a working repository have **no object id**:

| Thing | What it has instead |
| --- | --- |
| The index | A file identity — device, inode, size, mtime — but no content hash |
| The working tree | Nothing; files change underneath a read |
| A remote URL | A name for a repository that is not local yet |
| A position in an ordered walk | An offset that is only meaningful while the walk lives |

Every hard problem outside the implemented surface descends from this one fact, and each
is solved the same way: **manufacture an identity, then state its validity rules.** A
manufactured identity is not a content hash and must never be treated as one — it may
not be used as an immutable cache key, and a document built from it carries a
`generation` rather than an `id`.

## The subprocess boundary

`metabrowser/git/process.py` is the only place a `git` process is created.
That singularity is what makes the properties below invariants rather than conventions
somebody has to remember, and it is why a new Git feature extends the module instead of
adding a second wrapper.

The module exposes two seams, and which one a feature needs is a real decision:

- **`run_git`** runs a command to completion and returns its buffered bytes.
  Every bounded, request-scoped read uses this.
- **`spawn_git_process`** returns a live process whose streams the caller owns, for
  consumers that cannot wait for completion — a long walk read page by page.
  It performs the same executable lookup, environment isolation, fixed-argument
  assembly, and spawn-failure translation, so the guarantees below are identical either
  way. Its `pipe_stdin` is reserved for bounded, already-validated input.

A caller that owns a process also owns terminating it; `terminate_git_process` is the
counterpart, and anything holding a process across requests needs the lifecycle rules in
[Long-lived walks](#long-lived-walks).

| Invariant | Mechanism | What it prevents |
| --- | --- | --- |
| No shell | `create_subprocess_exec`, fixed argv | A path or URL becoming a command |
| No ambient repository | Scrub `GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY`, `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_PREFIX`, `GIT_NAMESPACE`, `GIT_CEILING_DIRECTORIES` | Reading a different repository than the one addressed; git exports these to child processes |
| No lock contention | `--no-optional-locks` and `GIT_OPTIONAL_LOCKS=0` | A browser read blocking a terminal git command, and any index write |
| No hanging prompt | `GIT_TERMINAL_PROMPT=0`, empty `GIT_ASKPASS`, empty `SSH_ASKPASS` | A credential prompt stalling a server request forever |
| Bounded output | Incremental cap at `GIT_SUBPROCESS_MAX_BYTES`, 64 KiB read chunks | An unbounded buffer from a hostile or huge repository |
| Bounded time | `GIT_SUBPROCESS_TIMEOUT_S`, then terminate and reap | A wedged process outliving its request |
| No deadlock | Concurrent stdout/stderr draining | Both pipes filling while one is unread |
| No leaked paths | stderr capped at 64 KiB and only ever logged | Absolute local paths reaching a JSON body |

Failures are typed rather than string-matched: `GitUnavailableError`, `GitCommandError`,
`GitTimeoutError`, and `GitOutputTooLargeError`, all under `GitError`. Callers branch on
the type, so “git is not installed” and “this is not a repository” stay distinguishable
from “the command failed.”

`run_git` returns **bytes**. That is load-bearing, not an accident of implementation.

### One consequence worth knowing

`GIT_OPTIONAL_LOCKS=0` is what makes reads genuinely observational: plain `git status`
rewrites `.git/index` to persist a refreshed stat cache, and with optional locks off it
does not. The cost is that the stat cache never persists, so stat-dirty files re-hash on
every invocation. Any feature that polls Git must budget for a cost that does not
amortize.

### Long-lived walks

Continuous history is the first consumer that holds a Git process across requests, and
it is worth reading as the third instance of the identity problem above rather than as a
special case. A page of `git log` output has no object id: its offset means something
only while that ordered walk exists.
So the position gets a manufactured identity — an opaque page cursor — and the cursor
carries the rules that say when it stopped being true.

`git/history.py` owns one demand-driven `git log --date-order` walk per session.
Pages already produced are framed into a private spool and replayed by indexed seek, so
revisiting a page is a file read rather than a re-walk.

The cursor is base64-encoded JSON carrying a format version, the session id, a scope
fingerprint, the page number, and the page size.
It is opaque to the browser and is validated on the way back in — exact key-set match, a
version check, regex-bounded ids, integers that reject `bool`, and a page size that must
equal the request’s own clamped limit.
Every invalid shape decodes to `None` rather than raising.

Four typed failures keep the states distinct, because “your cursor is malformed”, “the
session was evicted”, “the repository moved underneath you”, and “the replay budget is
exhausted” call for different recovery:

| Failure | Means |
| --- | --- |
| `InvalidHistoryCursorError` | The cursor is malformed, or disagrees with the request |
| `ExpiredHistorySessionError` | The bounded session is gone — idle-reaped, evicted, or shut down |
| `StaleHistorySessionError` | The repository or ref scope changed after the session was created |
| `HistoryStorageError` | The session exhausted its measured replay-storage budget |

Every resource a session holds is separately bounded, and the constants live in
`settings.py` beside the measurement that produced them: session count and concurrent
walks, idle TTL, replay storage, and a parser budget that scales with page size.
A session owns a process, a spool directory, and a registry entry, and all three are
released together on eviction, idle reap, and shutdown.
Shutdown drains the process output before reaping it — a walk whose stdout pipe is full
will not exit on its own, so reaping first would wait forever.

The rule this establishes for anything that follows: **holding a Git process across
requests means owning its whole lifecycle.** Bound the count, bound the storage, expire
on idle, release on shutdown, and give the client a typed way to learn its handle went
away — the client must be able to recover, not just fail.

## Paths are bytes

A POSIX path is an arbitrary byte sequence excluding NUL and `/`. It need not be valid
UTF-8. The convention that follows is uniform across the Git and diff layers:

- Identity, sort order, and comparison operate on **raw bytes**.
- Display is a separate, lossy projection: `path` for UTF-8 display, plus `path_b64`
  carrying the exact bytes when the two differ.
- HTML and URL output always escape the display string.

Two decoding disciplines coexist for good reasons.
Commands whose output is line-oriented run with `core.quotepath=false`, so git emits
UTF-8 directly instead of octal-escaping every non-ASCII byte and forcing each parser to
unescape. Commands that must survive arbitrary bytes use `-z` NUL framing instead, which
emits paths verbatim — and under `-z` `core.quotepath` has no effect, because there is
no quoting to suppress.

Object ids are full: 40 hexadecimal characters for SHA-1 repositories and 64 for
SHA-256. Abbreviations come from git itself via `short_id`, which respects the
repository’s `core.abbrev` and grows as the repository does; truncating client-side
would eventually collide.

## Discovery and the exact-root gate

`metabrowser/git/repo.py` resolves `rev-parse --show-toplevel` and compares it to the
served root. A repository is Git-capable only when the two are **equal**.

That gate is deliberate and load-bearing.
History is repository-wide, so serving a subdirectory as a Git root would let the Git
view enumerate commits and files outside the tree the user is allowed to browse.
Widening it is not a convenience change; it is a containment change.

Discovery resolves to one of four negative reasons — `no_git`, `not_a_repo`,
`not_repo_root`, `git_failed` — and never to an exception at the route layer.
Linked worktrees work because discovery uses Git’s own resolution rather than assuming a
literal `.git` directory; anything reading per-worktree control files must resolve them
through `git rev-parse --git-path` for the same reason.

## The collection API

Four read-only routes, registered as `GIT_ROUTES` in `metabrowser/git/routes.py`:

| Route | Serves |
| --- | --- |
| `/api/git/repo` | Repository presence and `HEAD`; the gate for everything else |
| `/api/git/refs` | Branches and tags |
| `/api/git/log` | One page of history, cursor-paginated |
| `/api/git/commit/{revision}` | One commit’s detail and change set |

`tests/test_git_arch_doc.py` compares this table to `GIT_ROUTES`, so the document fails
the build rather than drifting.
The routes also appear in the [views/models/routes map](arch-views-models-routes.md),
which `tests/test_views_models_routes.py` checks.

Four rules hold across all of them:

- **`/api/git/repo` is the gate.** When it reports `is_repo: false` the browser never
  renders the Git tab, and every other route returns the same negative envelope with
  **HTTP 200**. “Not a repository” and “git is not installed” are ordinary states of the
  world; a 4xx would route them into the browser’s error path.
- **Revisions are validated before reaching an argument vector.** `is_full_revision`
  accepts only full SHA-1 or SHA-256 object ids, so a caller-supplied value can never be
  read as an option or a revision expression.
- **Numeric parameters are clamped, not rejected.** An out-of-range `limit` is a client
  bug that should still render a panel.
- **Git failures become 5xx with a generic body.** Git’s error text contains absolute
  local paths, so it is logged and dropped.

## How the layers are modeled

The three tiers currently use three different modeling idioms.
That is worth stating plainly, because the differences are not all deliberate.

| Layer | Module | Idiom | What enforces it |
| --- | --- | --- | --- |
| File Diff Format | `diff/format.py` | Pydantic `BaseModel`, `extra="forbid"`, `frozen=True`, a `StrEnum` per closed vocabulary | The model itself, plus a JSON Schema and a conformance corpus |
| Git wire | `git/wire.py` | `TypedDict` with `NotRequired`, plus hand-written validators and `_*_REQUIRED` gate sets | Validators, exercised by the test suite |
| Cache and provider records | designed only | Pydantic plus deterministic compiled SoftSchema contracts | Compile-drift, corpus validation, and installed-wheel checks |

**The format layer is the model to copy.** Every closed vocabulary is a `StrEnum`
(`ChangeKind`, `SnapshotKind`, `Availability`, `EntryType`, `FileMode`, `LineOp`,
`DiffAlgorithm`, `BasePolicy`, `ContentRefKind`), `extra="forbid"` makes an undeclared
field an error rather than a silent pass, and `frozen=True` means a resolved comparison
cannot be mutated after validation.
Structural rules that a type cannot express — which sides each `ChangeKind` requires,
and that `renamed`/`copied` carry a similarity — are `model_validator` checks enforced
by the schema and both implementations.

**The Git wire layer’s idiom is a real trade, not an oversight.** `TypedDict` gives
producers static required-key checking while they build plain dicts, and those dicts go
straight onto the wire with no object construction — which matters for a log page
carrying hundreds of commits, where per-row model construction is measurable.
The cost is that `_*_REQUIRED` gate sets restate the class bodies, so there are two
sources of truth that a human keeps in sync; the module says so itself.

The standing rule for new Git models: **default to the `diff/format.py` idiom.** Reach
for `TypedDict` only where a producer streams many rows and the measured construction
cost justifies it — and when you do, say so at the module level and keep the duplicated
gate set in one obvious place.
A hand-synced invariant that is not documented as one is how these drift.

Lane assignment, row geometry, and colour are deliberately **absent** from the Git wire
model. Lane assignment is a pure function of the commit list and its ordering and is
naturally incremental across pages, so it belongs to the rendering layer
(`static/git-graph.js`). The wire carries facts; the browser derives presentation.

## Comparison sources

`DiffSource` in `diff/adapters/base.py` is the port, and it is four methods with no
source-specific vocabulary:

```python
async def resolve(self, intent: dict[str, Any]) -> ResolvedComparison: ...
async def manifest(self, resolved: ResolvedComparison) -> ChangeSetManifest: ...
async def file_patch(self, resolved: ResolvedComparison, file_id: str) -> FilePatch: ...
def content(self, resolved, file_id, side) -> AsyncIterator[bytes]: ...
```

That smallness is the point: it is what keeps patch-file, Git, hosted, and document-edit
sources interchangeable.
An intent is adapter-specific and arrives as plain data; everything a source returns is
File Diff Format. There is no central source registry — adapters are wired at their call
sites — so the port, not a table, is the contract.

Two sources exist today: `adapters/patch_file.py` and `adapters/git.py`, the latter
accepting revision intents only.

### Adding a source

A new source must answer four questions before it is written, because each one is a
failure mode that is expensive to retrofit:

1. **What is the identity?** If the source has content-addressed ids, use them.
   If it does not, manufacture one and say what it covers.
2. **When does that identity go stale, and how is staleness detected?** A source over
   mutable state must sample the relevant identities before and after materialization
   and return the `stale` availability rather than a document mixing two states.
3. **What are the snapshot kinds?** `SnapshotKind` already covers `commit`, `tree`,
   `index`, `worktree`, `patch`, and `empty` — the common cases are present, and adding
   a kind is a format change requiring its own review.
4. **What does it do when it cannot produce?** The `Availability` vocabulary — `ready`,
   `deferred`, `binary`, `too_large`, `timed_out`, `failed`, `stale`, `unsupported` — is
   the complete set of honest answers.
   Silently substituting an inferior rendering is not among them.

The rule that binds all four: **no source-specific field enters File Diff Format.** If a
source needs to carry something the format has no room for, that fact belongs in the
source’s own response alongside the document, not inside it.
The moment a source-neutral format grows a source-specific field, it stops being
source-neutral, and the renderer starts having to know what produced its input.

## The provider boundary

**Status: designed only.** No provider code exists.
The design lives in the
[repository library plan](../specs/active/plan-2026-08-11-open-repo-from-git-url.md) and
the
[design review](../reviews/review-2026-08-26-repository-library-and-github-model.md);
this section records only the boundary those documents must not cross, because that
boundary is an architectural commitment rather than a plan detail.

A provider may:

- describe hosted state that Git does not model — reviews, checks, threads, decisions;
- refer to Git content by immutable object id; and
- own its own schemas, adapters, routes, renderers, and styles as plugin-owned surfaces.

A provider may not:

- become authoritative for content, history, or diffs, which stay Git’s;
- store raw API responses as the durable model, which would make transport shape the
  domain;
- require core to import a provider schema or branch on a provider object kind; or
- make generic acquisition, identity, refresh, or purge depend on it.

When provider code lands, it gets its own architecture document rather than a section
here — one subject per document, and a provider content model is a different subject
with a different lifetime from the Git boundary.

## Invariants

The short list a change should be checked against:

1. Every `git` invocation goes through `git/process.py`, via `run_git` or
   `spawn_git_process`. A subprocess spawned anywhere else is a bug, and
   `tests/test_git_arch_doc.py` fails the build for one.
2. Argument vectors are fixed; caller-supplied values are validated before they can be
   read as options or revision expressions.
3. Paths are bytes for identity and comparison; UTF-8 only for display, with `path_b64`
   when they differ.
4. A Git-capable root is the repository’s exact working-tree root.
5. Absent repository states are HTTP 200 negative envelopes; only genuine failures are
   5xx, and Git’s stderr never reaches a body.
6. Anything without an object id carries a `generation`, never an `id`, and is never
   used as an immutable cache key.
7. File Diff Format gains no source-specific field.
8. Providers reference Git; Git does not reference providers.

## Related documentation

- [Views, models, and routes](arch-views-models-routes.md) — the map, and where these
  routes are registered
- [File Diff Format v1](file-diff-format/file-diff-format.md) — what a comparison
  document is
- [Diff sources, context, and anchoring](file-diff-format/diff-sources-and-anchoring.md)
  — provenance and anchoring within the diff pipeline
- [State and delivery](arch-state-and-delivery.md) — the inventory, invalidation, and
  the browser’s state layers
- [Browser URL grammar](../../architecture.md#browser-url-grammar) — how comparisons are
  addressed
- [Repository library and open from a Git URL](../specs/active/plan-2026-08-11-open-repo-from-git-url.md)
  — the designed cache and provider work
- [Git status and working-tree diffs](../specs/active/plan-2026-08-26-git-status-and-working-tree-diffs.md)
  — the designed working-tree comparison source

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
