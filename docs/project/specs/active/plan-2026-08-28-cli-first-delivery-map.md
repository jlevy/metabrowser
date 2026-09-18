# Plan: CLI-First Delivery — v0.10 Parity and the v0.11 Repository/Hosted-Review Slice

**Date:** 2026-08-28 (refreshed 2026-09-16)

**Author:** Joshua Levy (with LLM assistance)

**Status:** v0.10.0 released and the parity foundation landed; v0.11.0 implementation is
active

## Overview

The CLI parity mechanism and its route, kind, model, persisted-state, and functional
aspect checks shipped in v0.10.0. The remaining workstreams are
[Git status](plan-2026-08-26-git-status-and-working-tree-diffs.md), the
[repository library](plan-2026-08-11-open-repo-from-git-url.md), and the
[hosted-review and GitHub provider](plan-2026-08-27-github-provider-and-pull-requests.md).
This document records the delivered foundation, sequences the v0.11.0 PR-first slice,
and states how backend work is proved end to end without a browser.

The thesis is that the parity plan is not a testing chore that follows the features.
It is the delivery mechanism for them.
Land `--api` first, behavior-preserving, and every route the status and cache work adds
is reachable and golden-testable the day it exists, with no per-feature test harness.

One rule follows from that and is the main structural claim here:

> **Prefer a new route to a new CLI mode.** `--api <route>` reaches every registered
> route by construction.
> A surface exposed as a route is inspectable and pinned by a golden for free; a surface
> exposed only as a CLI mode needs its own flag, its own normalizer path, and its own
> golden.

That rule is what lets cache state — the part of this work with no natural UI — be
tested as rigorously as the parts that have one.

## The Parity Principle, Extended

The [parity plan](../done/plan-2026-08-21-cli-parity-and-golden-coverage.md) states the
principle over the four layers `route → kind → model → view`, and exempts only the view.
That covers read models.
It does not cover **durable state**, which is most of what the cache is.

The cache writes an application home, layout and source/store identity and state
records, locks, staging directories, quarantine, and trash.
None of that appears in a response envelope, so a `--api` transcript proves nothing
about it. The principle needs a second clause:

> **State clause.** Every state the system persists is reachable from `metab` as a
> normalized model and pinned by a golden transcript.
> Cache layout, source and store identity, publication and job state, and reclamation
> outcomes are read through `/api/cache/*` like any other model, not through a bespoke
> inspection command.

This is why the cache gets read routes in Phase 1A, before anything can be cloned.
The routes are cheap — they project records the format foundation already writes — and
they turn the entire state machine into something a transcript can assert.

## Ordering

Row 1 and the landed portion of row 2 are the v0.10.0 baseline; `mb-n9xg` continues the
legacy functional-parity inventory.
For v0.11.0, the table’s *Gated by* column is authoritative where this prose and it
disagree; independent status, format, trust, and provider-model work can proceed in
parallel.

| # | Work | Beads | Gated by | State |
| --- | --- | --- | --- | --- |
| 0 | v0.11 start gate: v0.10.0 tag and release from intended `main` | `mb-i57d`, `mb-xxhi` | nothing | Complete 2026-09-15; v0.10.0 released and the implementation baseline verified |
| 1 | Parity mechanism: ASGI client, normalizer, `--api`, `--show` | `mb-8n8l`, `mb-ian3`, `mb-y5wm` | nothing | Landed on `main` for v0.10.0 |
| 2 | Parity enforcement, persisted state, functional aspects, and codification | `mb-esht`, `mb-zodq`, `mb-n9xg` | 1 | Enforcement and codification landed for v0.10.0; `mb-n9xg` remains active for legacy functional inventory |
| 3 | Git-status measurement gate | `mb-r5gn` | 0 | v0.11.0 |
| 4 | Git-status backend, then panel | `mb-u4mf`, `mb-vibn`, `mb-y06t` | 0, 1, 3 | v0.11.0 foundation |
| 5 | Measurement and source-binding correction, owner-only cache format, local-origin contract, worktree-free acquisition, content-source boundary, then immutable Git-tree source | `mb-ire2`, `mb-z2mc`, `mb-xa0p`, `mb-4gnu`, `mb-k54c`, `mb-dxmb`, `mb-h51g`, `mb-dg00`, `mb-3bna`, `mb-z335` | 0, 1 | v0.11.0 |
| 6 | HTML trust chain | `mb-cun0`, `mb-vib1`, `mb-d658` | 0 | Gates serving fetched content; publishes as its own stack layer after row 5 |
| 7 | Provider URL reducer, repository open, provider-selected refs, then immutable selected branch | `mb-12cz`, `mb-ew38`, `mb-jlon`, `mb-2xq7` | 5, 6 | v0.11.0 |
| 8 | Hosted-review models | `mb-63ym` | 0 | v0.11.0 |
| 9 | Bounded provider runner, `gh api` adapter, broker-pinned Git credential bridge, capability registry, auth-scoped store, repository summary, then direct PR bundle | `mb-y1ax`, `mb-p4sw`, `mb-s123`, `mb-ji83`, `mb-s0gv`, `mb-i3xc`, `mb-2oxp`, `mb-cbak`, `mb-h64t` | 5, 7, 8 | v0.11.0 |
| 10 | Plugin router, address-space lifecycle, and direct PR document/diff | `mb-xzj3`, `mb-6mle`, `mb-81p5` | 6, 9 | v0.11.0 |
| 11 | Query-keyed bounded PR index and virtual nav | `mb-lnkl`, `mb-uh6p`, `mb-iw1v` | 9, 10 | v0.11.0 |
| 12 | Anchored review threads | `mb-rldc` | 10 | v0.11.0 |

Row 6 is the
[R1 finding](../../reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md):
serving fetched content is gated on the trust chain, which no plan prioritized.
It depends on nothing here, so it runs alongside rather than extending the schedule.

The *lift* in row 1 was behavior-preserving, and that remains checkable: every existing
golden, `cli-check-api.tryscript.md` among them, must be byte-identical after it.
If a transcript moves, the lift changed behavior and the change is wrong.

The rows as a whole are not behavior-preserving, and an earlier draft said they were.
They add two modes, so `cli-surface.tryscript.md` changes and `CHANGELOG.md` gains an
entry. The invariant is about the refactor, not the phase.

## Part 0: Delivered Parity Mechanism — Module and Function Map

### `src/metabrowser/cli/asgi_client.py` (new)

Lifted verbatim from the private `_InProcessClient` in `cli/check_api.py`, which keeps
`--check-api` on exactly the code it runs today.

```python
@dataclass(frozen=True, slots=True)
class ApiResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes

    def json(self) -> Any: ...

class InProcessClient:
    def __init__(self, app: ASGIApp) -> None: ...
    async def get(self, url: str) -> ApiResponse: ...
    async def post(self, url: str, *, body: bytes) -> ApiResponse: ...

async def wait_for_index(client: InProcessClient, *, timeout_s: float) -> IndexResult: ...
```

`post` lands here now rather than later because it costs nothing at lift time and closes
the plan’s first open question: `/api/kpress/render` and `/api/kpress/export` are
POST-only and would otherwise be permanently exempt.

### `src/metabrowser/normalize.py` (new)

The session schema the golden guidelines ask for, stated once.

```python
@dataclass(frozen=True, slots=True)
class NormalizeContext:
    root: Path

CURSOR_PATHS: tuple[tuple[str, ...], ...]   # addressed by position, not key name
ELAPSED_PATHS: tuple[tuple[str, ...], ...]

def normalize_payload(value: Any, ctx: NormalizeContext) -> Any: ...
def normalize_text(text: str, ctx: NormalizeContext) -> str: ...
```

The rules, and why each is needed:

| Field or shape | Becomes | Why |
| --- | --- | --- |
| Absolute path under `root` | `<ROOT>/...` | sandbox path varies |
| Envelope `page_cursor`, `cursor`, `previous_cursor` | `<CURSOR>` | a random session token; no fixture can pin it |
| Envelope `inventory.elapsed_ms`, `inventory.duration_ms` | `<ELAPSED>` | wall clock; moves with load and hardware |
| Git revisions | **kept** | fixture repos are built deterministically |
| Absolute path under `home` | `<HOME>/...`, **Cache 1A** | cache home varies |
| `mtime`, `mtime_hash` | `<MTIME>`, **opt-in, Cache 1B-a** | fixtures pin these with `touch -t`; a clone into the cache cannot |

The last two rows are added to `normalize.py` with the cache goldens that first need
them (`mb-dg00`): `<HOME>` with `cli-cache-layout` in Cache 1A, and the opt-in `<MTIME>`
with `cli-cache-acquire` in Cache 1B-a. No `--api` or `--show` transcript has an
application home or an unpinnable mtime.

The table was measured, and then it grew, which is worth recording because the first
version of this paragraph did not.
Running the same routes twice against two sandbox roots, the only field that varied was
`root`. That sample was too small: `/api/git/log` carries a `page_cursor` holding a
random session token, and `/api/diagnostics/pending-tallies` carries
`inventory.elapsed_ms`, a wall clock.
Both were found later, by routes the first sweep did not request, and both are
normalized now. The lesson is about the method rather than the fields — “no envelope
carries X” is a claim about every envelope, and a sweep of six proves nothing of the
sort. Mtime normalization will be opt-in for a different and better reason: the existing
goldens pin mtimes with `touch -t` and assert the real values, so normalizing by default
would delete coverage a fixture already controls.

`metabrowser/normalize.py` is the authority for what is normalized; this table describes
it and can lag it.

Placeholders use angle brackets, not square ones.
tryscript reads `[NAME]` in expected output as an elision pattern, and `[ROOT]` is one
of its built-ins — it matches the test file’s directory rather than the served root — so
a square-bracket placeholder is silently reinterpreted instead of compared.
This was found by writing the first `--api` golden: the three cases carrying `[ROOT]`
failed while the three without it passed.

Keeping revisions is deliberate and is the single most valuable decision in the testing
design. See [Deterministic origin repositories](#deterministic-origin-repositories).
Normalizing them away would trip the first anti-pattern in
`tbd guidelines golden-testing-guidelines`: a pattern that hides a value you control
removes the coverage you were trying to add.

### `src/metabrowser/cli/api_cli.py` (new) — `mb-ian3`

```python
async def run_api(
    root: Path,
    *,
    route: str,
    fmt: str = "json",
    data: Path | None = None,
    plugins_dir: list[Path] | None = None,
    log_level: str = "",
    index_timeout_s: float = INDEX_READY_TIMEOUT_S,
) -> None: ...   # the index wait is per-route, not a flag
```

Builds the real app, waits for the index when the route needs one, issues the request,
normalizes, prints. Exit code carries the HTTP status class so a transcript asserts
failure honestly.

### `src/metabrowser/cli/show_cli.py` (new) — `mb-y5wm`

```python
async def run_show(root: Path, path: str, *, fmt: Literal["text", "json"]) -> int: ...
```

Reports the four layers for one selection: resolved route, kind, view list, model
summary. This is the command that finally pins `/api/file`, which decides the tabs a
reader sees and today is proved by nothing outside a browser.

### `devtools/check_parity.py` (new) — `mb-esht`

Enumerates registered routes by walking every module under `src/metabrowser/` for
`Route(` registrations, plus every manifest `[[data_hook]]`; reads the parity table in
[Views, Models, and Routes](../../architecture/arch-views-models-routes.md); fails
naming the surface when a row is missing, names a command the CLI rejects, or names a
command appearing in no golden.

### Edits

- `cli/main.py` — add `--api`, `--show`, `--format`, `--data`; root type unchanged in
  this phase.
- `cli/check_api.py` — import the shared client; delete the private copy.
- `AGENTS.md`, `docs/development.md` — the principle and its reasoning (`mb-zodq`).

## Part 1: Git Status — Module and Function Map

### Phase 0, the measurement gate (`mb-r5gn`)

`devtools/git_status_benchmark.py`, mirroring the existing
`devtools/git_history_benchmark.py` and pinned by `tests/test_git_status_benchmark.py`
the way `tests/test_git_history_benchmark.py` pins its sibling.
It builds dirty-tree corpora and records latency, bytes, and retained memory, which is
what closes the three open decisions (submodule inspection, the budgets, and whether
copy detection earns its cost).

### `src/metabrowser/git/status.py` (new) — Phase 1 (`mb-u4mf`)

```python
@dataclass(frozen=True, slots=True)
class StatusBounds:
    max_entries: int
    max_bytes: int
    timeout_s: float

@dataclass(frozen=True, slots=True)
class StatusEntry:
    xy: str                       # porcelain-v2 two-letter state
    path: bytes                   # arbitrary bytes, never str until projection
    orig_path: bytes | None       # rename/copy source
    score: int | None

@dataclass(frozen=True, slots=True)
class StatusResult:
    head: str | None              # None on an unborn branch
    entries: tuple[StatusEntry, ...]
    truncated: bool

def parse_porcelain_v2(data: bytes) -> Iterator[StatusEntry]: ...
async def read_status(ctx: RepoContext, *, bounds: StatusBounds) -> StatusResult: ...
```

`parse_porcelain_v2` is the risk concentration, and the reason is concrete.
It consumes `git status --porcelain=v2 -z --untracked-files=all`, whose records are
NUL-terminated but **not** uniformly one record per NUL field.
Verified against Git 2.50.1, a rename emits its two paths as two separate NUL-terminated
fields belonging to one record:

```text
2 R. N... 100644 100644 100644 <oid> <oid> R100 renamed.txt\0a.txt\0
1 A. N... 000000 100644 100644 <oid> <oid> weird name.txt\0
? u.txt\0
```

Splitting on NUL and treating each field as a record yields `a.txt` as a phantom entry
and desynchronizes everything after it.
The parser must be record-type driven: a leading `2` consumes two path fields, while
`1`, `u`, `?`, and `!` consume one.
It stays on `bytes` end to end; the projection to `str` happens once, at the wire
boundary, with a documented replacement policy for undecodable paths.
`read_status` goes through `run_git` like every other subprocess in the package, so
bounds, cancellation, and the `GitError` hierarchy come for free.

### `src/metabrowser/git/wire.py` (edit)

Follows the established TypedDict-plus-validator idiom:

```python
class GitStatusEntry(TypedDict): ...
class GitStatus(TypedDict): ...
def validate_git_status(status: Mapping[str, Any]) -> None: ...
```

### `src/metabrowser/git/routes.py` (edit)

```python
async def api_git_status(request: Request) -> JSONResponse: ...
# Route("/api/git/status", api_git_status)
```

### `src/metabrowser/diff/adapters/working_tree.py` (new)

One selected status entry as a File Diff Format document, reusing the patch-file parser
the way `adapters/git.py` already does rather than carrying a second one.

```python
class WorkingTreeSource(DiffSource):  # the Protocol in diff/adapters/base.py
    async def resolve(self, intent: dict[str, Any]) -> ResolvedComparison: ...
    async def manifest(self, resolved: ResolvedComparison) -> ChangeSetManifest: ...
    async def file_patch(self, resolved: ResolvedComparison, file_id: str) -> FilePatch: ...
    def content(
        self, resolved: ResolvedComparison, file_id: str, side: str
    ) -> AsyncIterator[bytes]: ...
```

Backed by `/api/plugin/diff/working-tree` in `builtin_plugins/diff/sidekick.py`.

### Phase 2 (`mb-vibn`) — the only browser work in this document

`static/git-panel.js` gains a grouped changes section above the virtualized history;
`static/git-status-rows.js` is new.
Everything beneath it is already proved by then.

## Part 2: Repository Cache — Module and Function Map

### `src/metabrowser/home.py` (new) — Phase 1A (`mb-4gnu`)

```python
def application_home() -> Path:      # METABROWSER_HOME, else ~/.metabrowser
def ensure_home(home: Path) -> Path: # creates the f01 skeleton, writes CACHEDIR.TAG
```

`METABROWSER_HOME` is the hermeticity seam for every cache golden.

### `src/metabrowser/cache/` (new package)

| Module | Responsibility | Key functions |
| --- | --- | --- |
| `layout.py` | Format record, fail-closed future formats, ordered migrations, home preparation | `read_layout`, `read_config`, `migrate_layout`, `open_cache`, `LAYOUT_FORMAT` |
| `atomic.py` | Same-filesystem owner-only record publication | `read_record`, `write_record_atomic`, `publish_entry` |
| `locks.py` | Fixed lock hierarchy, leases, and liveness locks | `application_home_lock`, `source_alias_lock`, `repository_store_lock`, `provider_resource_lock`, `store_lease`, `store_maintenance_lock` |
| `probe.py` | Application-home lock and publication probe | `probe_application_home` |
| `contracts.py` | Packaged SoftSchema bindings and drift checks | `compile_contracts`, `cache_contract_registry`, `repository_cache_capabilities` |
| `records.py` | Closed source/store and staged-fetch contracts | `ApplicationConfig`, `CacheLayout`, `RepositorySource`, `RepositorySourceState`, `RepositoryStoreAlias`, `RepositoryStore`, `RepositoryStoreState`, `StagedFetch` |
| `reclaim.py` | Startup staging/trash sweep, trash, quarantine, store reclamation, and lease-aware object reclamation | `reclaim_staging`, `reclaim_trash`, `quarantine_entries`, `reclaim_store`, `reclaim_unreferenced_stores`, `reclaim_repository_objects` |
| `identity.py` | Conservative source identity, provider-derived store identity, aliasing, and collision-safe slugs | `normalize_git_source`, `source_identity`, `repository_store_id`, `provider_repository_store_id`, `cache_slug` |
| `urls.py` | Root classification, provider reducer arbitration, and terminal rejection | `classify_root_argument`, `ProviderUrlReducer`, `ReducerOutcome`, `RepositorySelection` |
| `acquire.py` | Worktree-free staged acquisition and atomic store/alias publication | `acquire_repository`, `validate_staging_store`, `publish_store`, `publish_source_alias` |
| `repository_store.py` | Selected-object fetch jobs, full-OID publication, leases, convergence, and maintenance | `resolve_store`, `stage_fetch`, `publish_refs`, `lease_revision`, `converge_store`, `reclaim_objects` |
| `selection.py` | Pure ref/path resolution and typed missing-ref requests | `resolve_selection`, `resolve_ref_path_candidates` |
| `service.py` | One CLI/chooser orchestration result | `resolve_open_target`, `close_open_target` |
| `jobs.py` | Provider-neutral selected-ref jobs, the credential-lease registry and per-request validation, and stage outcomes | `RepositoryJob`, `RepositoryJobRegistry`, `fetch_selected_ref`, `request_ref_fetch`, `GitFetchCredentialLeaseRegistry`, `validate_git_fetch_credential_lease`, `close_all` |
| `routes.py` | Logical source, store, and job projections for CLI parity | `api_cache_layout`, `api_cache_sources`, `api_cache_source`, `api_cache_stores`, `api_repository_jobs` |

The session/content seams live outside the cache package:

| Module | Responsibility | Key functions |
| --- | --- | --- |
| `src/metabrowser/repository_context.py` | Active attached-filesystem or immutable-revision subject and its lifetime | `RepositorySubject`, `AttachedFilesystemSubject`, `GitRevisionSubject` |
| `src/metabrowser/content_source.py` | Generation-owned capability-aware reads without invented filesystem facts | `SourceSession`, `SourceCapabilities`, `ContentSource`, `ContentHandle`, `list_directory`, `read_window`, `close` |
| `src/metabrowser/git/process.py` | Sole trusted Git subprocess boundary and validated askpass projection isolated from ambient Git environment, configuration, and credential helpers | `GitCommandTarget`, `run_git`, `spawn_git_process` |
| `src/metabrowser/git/tree_source.py` | Raw-byte `GitPath` tree/blob access over a full OID in the shared store | `GitPath`, `GitTreeSource`, `resolve_tree`, `list_tree`, `read_blob` |
| `src/metabrowser/plugin_api.py` | Opaque provider credential capability and provider-to-job conversion | `GitFetchCredentialLease`, `provider_fetch_authorization_context`, `RepositoryObjectJobPort.request_selected_refs` |

The exact types, invariants, and phase ownership live in the
[repository plan](plan-2026-08-11-open-repo-from-git-url.md) and
[repository-source architecture](../../architecture/arch-repository-sources-and-provider-mirrors.md).
This map deliberately links to those authorities instead of duplicating signatures that
can drift.

`cache/routes.py` is the part that is easy to skip and should not be.
The read routes, written alongside the records they project, make every subsequent
source, store, and job behavior assertable from a transcript.

## Golden Testing Architecture

### A session is a tryscript file

The repository already runs `tests/golden/*.tryscript.md` under `make test`, restores
elisions with `devtools/golden_fixup.py`, and regenerates with `make golden-update`. No
new runner is needed.
A tryscript file with `sandbox: true` gives a fresh directory per run, and a sequence of
`$ metab ...` commands in it *is* the session: setup, action, and state inspection in
one reviewable document.

### Hermeticity

Every cache golden sets, in frontmatter `env`:

```yaml
METABROWSER_HOME: "./home"     # cache state lands in the sandbox
METABROWSER_PLUGINS_DIRS: ""   # no ambient plugins
TZ: "UTC"
GIT_CONFIG_GLOBAL: "/dev/null" # no developer gitconfig leaks in
GIT_CONFIG_SYSTEM: "/dev/null"
```

That makes the cache and Git behavior a pure function of the sandbox.
No network, no home directory, no machine-specific config.

### Deterministic origin repositories

A fixture repository built with pinned identity and dates produces **byte-identical
commit SHAs on every machine and every run**, because a commit hash is a function of its
tree, parents, author, committer, and message, and nothing else:

```bash
export GIT_AUTHOR_NAME=Test GIT_AUTHOR_EMAIL=test@example.com
export GIT_COMMITTER_NAME=Test GIT_COMMITTER_EMAIL=test@example.com
export GIT_AUTHOR_DATE='2020-01-01T00:00:00Z'
export GIT_COMMITTER_DATE='2020-01-01T00:00:00Z'
git init -q --initial-branch=main origin
```

Verified on Git 2.50.1: two repositories built from the same commands produced identical
HEADs. The literal hash is not quoted here, because it is determined by the tree and
message as well as the recipe, so a reader could not reproduce it from what is shown —
the reproducible claim is the equality, not the value.
So Git goldens assert **real revisions**, not `<REV>` placeholders.
A commit that changes shape changes the golden, which is the entire point.
`--initial-branch=main` is required: the default branch name varies by Git version and
is the one genuinely unstable thing in the recipe.

What is *not* stable, and must never be asserted: pack file names, `.git` internal
layout, object counts after gc, and clone wall time.
`cache/routes.py` therefore projects **logical** source, store, alias, job, and revision
state and never a cache-directory listing.

### Acquisition without a network

`acquire` clones from a local origin repository created in the same sandbox.
This is real `git fetch` through the real `run_git`, with no mocking and no forked code
path, which is what the golden guidelines mean by not forking logic for tests.
It also happens to be the honest test: the failure modes that matter — partial clone,
interrupted publish, quarantine, reuse-on-second-open — are all filesystem behavior, not
network behavior.

A live `metab file:// --no-serve` tryscript cannot run on ubuntu-latest today: the
runner’s Git 2.43.0 is below the acquisition floor (2.43.7 / patched tracks), and
distro-patched Git remains refuse.
Until CI pins Git 2.50.1 (`mb-oueh`), acquire / reuse / staging-sweep / orphan-store
reclaim evidence is `tests/test_cli_cache_acquire_golden.py`: the production CLI
in-process, the floor monkeypatched, a real pack fetch.
Layout and future-format refusal remain `cli-api-cache.tryscript.md`. Do not add
`<HOME>` or `<MTIME>` to `normalize.py` until a transcript emits those values; cache
routes never report paths, and `--no-serve` does not print the home.

### What each phase’s golden proves

| Golden | Proves | Phase |
| --- | --- | --- |
| `cli-api.tryscript.md` | `--api` reaches every registered route; envelopes are stable | Parity |
| `cli-show.tryscript.md` | kind and view list for one file of each built-in kind | Parity |
| `cli-git-status.tryscript.md` | conflicts, staged, unstaged, untracked, renames, unborn HEAD, binary, submodule | Status P1 |
| `cli-git-status-bounds.tryscript.md` | truncation is honest and reported, not silent | Status P1 |
| `cli-cache-layout.tryscript.md` | home creation, `f01` record, `CACHEDIR.TAG`, future-format refusal | Cache 1A |
| `cli-cache-acquire.tryscript.md` | clone, publish, second open reuses with no network | Cache 1B-a |
| `cli-cache-recover.tryscript.md` | interrupted publish quarantines; reclaim sweeps staging | Cache 1B-a |
| `cli-url-open.tryscript.md` | URL grammar accepts and rejects, with reasons | Cache 1B-b |
| `cli-github-repo-open.tryscript.md` | GitHub repository URL reduces to and reuses the shared store without provider auth | Repository 2A |
| `cli-github-branch-open.tryscript.md` | default, non-default, slash-containing, offline, and unavailable branches use immutable revision subjects without moving a checkout | Repository 2C |
| `cli-github-pr-open.tryscript.md` | a direct PR selection publishes one bundle and fetches only selected refs without an index | GitHub P3B |
| `cli-github-pr-index.tryscript.md` | bounded pages, freshness, completeness, and no ref fetch while listing | GitHub P3C |
| `cli-github-pr-offline.tryscript.md` | repository and selected PR remain inspectable from immutable snapshots without a network | GitHub P4A |
| `cli-ui-hosted-review.tryscript.md` | exact production address parse/apply, direct view, panel window/selection/restoration, root replacement, and disposal | GitHub P4 |

`cli-cache-recover` is the one worth insisting on.
Crash recovery is the behavior most likely to be wrong and least likely to be exercised
by hand, and a transcript that kills a publish midway and then shows the swept state is
a far better test than any unit test of the same code.

## Codifying the Principle

`mb-zodq` adds to `AGENTS.md`, pointing at the check rather than restating it:

> Every route, kind, and model the browser consumes, and every state the system
> persists, has a `metab` equivalent and a golden transcript.
> Prefer adding a route to adding a CLI mode: `--api` reaches routes by construction.
> `devtools/check_parity.py` enforces this and names what is missing; the exemption list
> and its reasons live in `docs/project/architecture/arch-views-models-routes.md`.

The reasoning — the four layers, why the view is exempt, why state needed its own clause
— goes in `docs/development.md`, which today does not mention parity at all.

## Execution Plan

The map above says what to build.
This section says how it gets built without supervision, and — more usefully — where
unsupervised work must stop.

### The loop, once per bead

1. Read the bead and the spec section it names.
   The bead is the unit of work; the spec is the authority.
2. Write the golden first, as a failing transcript.
   It is the acceptance criterion, so it is written before the code that satisfies it
   and reviewed as a specification in its own right.
3. Implement until the transcript passes.
4. Run `make verify`.
5. Review the golden diff line by line, then commit code and transcript together.
6. Close the bead, `tbd sync`, and move to the next ready one.

### The one discipline that matters

`make golden-update` rewrites transcripts to match current behavior.
Run it to record an *intended* change, never to make a failure go away.
A regenerated golden that nobody read is worse than no golden: it converts a regression
into a committed expectation, and the next reader inherits it as the specification.

So: when a transcript changes, the diff is read line by line and the change is explained
in the commit message.
When a transcript changes in a way that was not intended, that is a bug found, not a
transcript to refresh.
This is the failure mode `tbd guidelines golden-testing-guidelines` names
“over-approval,” and it is the one that makes golden suites worthless over time.

### Behavior preservation is checkable, not aspirational

`mb-8n8l` lifts `_InProcessClient` out of `check_api.py`, and `mb-ian3` and `mb-y5wm`
build on it. Across all three, every existing transcript in `tests/golden/` must stay
byte-identical. That is the whole test: if `cli-check-api.tryscript.md` moves, the lift
changed behavior and the change is wrong, whatever the diff looks like.

### Where unsupervised work stops

These are not risks to manage; they are decisions that are not the implementer’s to
make. Work up to them, then stop and report with the evidence gathered.

SoftSchema adoption is no longer a stop.
The owner has confirmed the `jlevy` first-party exemption from the 14-day delay;
`mb-4gnu` still reviews and records the exact release, predecessor, lock delta,
dependencies, artifacts, and runtime reach before adoption.

| Stop | Bead | Why it is not an implementation decision |
| --- | --- | --- |
| Unbounded `--untracked-files=all` | `mb-r5gn` | The plan says that if a complete status cannot be bounded usefully, the phase returns to design review. Choosing a partial-status policy instead would be redesigning the feature. |
| Any `PLUGIN_SDK_VERSION` bump | any | A hard gate by [AGENTS.md](../../../../AGENTS.md), not a compatibility layer to negotiate. Optional additive declarations may retain SDK 0.6 only when existing manifest and JavaScript behavior is unchanged and plugin docs plus `CHANGELOG.md` are updated. |
| A golden that changes for an unexplained reason | any | Either a regression or a misunderstanding of the spec. Both need a human before the transcript is rewritten. |

Everything else is ordinary work: the budgets from `mb-r5gn` are chosen from recorded
measurements, and the rename-versus-copy question is answered by whether copy detection
measures cheaply enough on the corpus.
Those are decisions with evidence attached, so they get made and recorded rather than
escalated.

### What landed for the parity foundation

The first five beads established the baseline now on `main` for the v0.10.0 release
candidate:

| Order | Bead | Done when |
| --- | --- | --- |
| 1 | `mb-8n8l` | `InProcessClient` and `normalize.py` exist; every existing golden byte-identical |
| 2 | `mb-ian3` | `metab . --api '<route>'` reaches every registered route; `cli-api.tryscript.md` green |
| 3 | `mb-y5wm` | `--show` reports route, kind, views, model; `cli-show.tryscript.md` covers one file per built-in kind |
| 4 | `mb-esht` | `check_parity.py` fails on a missing row, a bad command, and an unpinned row; wired into `make lint-check` |
| 5 | `mb-zodq` | The three clauses in `AGENTS.md`, the reasoning in `docs/development.md` |

### What lands for the v0.11.0 PR-first slice

`mb-i57d` and `mb-xxhi` closed on 2026-09-15 after v0.10.0 was released and the intended
`main` baseline was verified.
The remaining sequence proceeds from that released baseline:

1. Run the status measurements (`mb-r5gn`) while the cache format and trust tracks begin
   independently.
2. Complete cache measurement, then land the source-binding correction, owner-only
   application-home records, local-origin contract, worktree-free store, source-session
   boundary, immutable Git-tree source, and URL-open foundation (`mb-ire2`, `mb-z2mc`,
   `mb-xa0p`, `mb-4gnu`, `mb-k54c`, `mb-dxmb`, `mb-h51g`, `mb-dg00`, `mb-3bna`,
   `mb-z335`, `mb-12cz`, `mb-ew38`). Then land the provider job/ref owner (`mb-jlon`)
   before selected-branch integration (`mb-2xq7`). No phase creates or switches a
   checkout for cached revision browsing.
3. Land the provider-neutral hosted-review contracts (`mb-63ym`) and narrow provider
   jobs/ref fetching (`mb-jlon`) without waiting for full cache management.
4. Publish the bounded provider runner, `gh api` adapter, broker-pinned Git credential
   bridge, capability registry, auth-scoped store kernel, repository summary, and one
   directly addressed PR bundle (`mb-y1ax`, `mb-p4sw`, `mb-s123`, `mb-ji83`, `mb-s0gv`,
   `mb-i3xc`, `mb-2oxp`, `mb-cbak`, `mb-h64t`).
5. Add the mounted plugin router, browser address-space lifecycle, and direct PR
   document/diff (`mb-xzj3`, `mb-6mle`, `mb-81p5`) after the content-trust serving gate
   is satisfied. This is the first complete PR workflow and does not wait for a discovery
   index.
6. Add the bounded PR index and virtual Pull Requests collection (`mb-lnkl`, `mb-uh6p`,
   `mb-iw1v`), then layer anchored review threads (`mb-rldc`).

Full cache management, the chooser, GitHub issues and timelines, stacked PRs, and
very-large-repository work remain later beads rather than hidden prerequisites.

## Open Decisions

**Closed 2026-08-28, revised 2026-08-30: `file://` origins are first-class Git sources;
bare local paths are not.** `cache/urls.py` classifies transport into `https`, `ssh`,
and `file`, and `acquire` binds a `file` source to the untrusted profile
unconditionally. `metab /path/to/repo` keeps meaning “serve that directory”, so the
grammar has no ambiguity to resolve.

The first draft accepted bare paths as well, calling them strictly safer than the
allowed transports. Review showed that wrong: `git clone` given a path defaults to
`--local`, which hardlinks `.git/objects` into the clone — so the entry is not isolated
from later mutation of the source — and ignores `--filter`, defeating blobless
acquisition with only a warning.
Both were reproduced on Git 2.50.1. `file://` uses the git-aware transport and packs
rather than hardlinks, which is what makes the testing rationale true.

`file://` honors `--filter` only when the origin allows it, so sandbox origins that
exercise blobless fetch set `uploadpack.allowFilter=true`. Measured on Git 2.50.1, an
origin without it sent every object with only a warning while the store still recorded
itself as a promisor.
Object-ID wants for prefetch and convergence need no further permission under protocol
v2, Git’s default above the acquisition floor; under protocol v0 the same blob wants
were refused with `Server does not allow request for unadvertised object` unless the
origin also set `uploadpack.allowAnySHA1InWant`, so goldens do not force v0
([measurements](../../../explorations/repository-cache/README.md#gitlinks-and-rejected-object-requests)).
See
[Safety at the boundary](plan-2026-08-11-open-repo-from-git-url.md#safety-at-the-boundary).

Portable acquire goldens (`mb-3639`) use an origin that does *not* allow the filter, so
`strategy` is `full` on every Git that can fetch at all.
Blobless honor/ignore remains a unit-test assertion, because ubuntu-latest’s Git 2.43.0
is below the acquisition floor.

**Closed 2026-09-18: acquisition is a side effect of `metab <url>`, with `--no-serve`.**
`--no-serve` acquires a `file://` source and prints logical identity without starting
the ASGI server. `metab file://… --api /api/cache/…` acquires, then inspects cache state
against an empty throwaway root.
There is no `/api/cache/acquire` write route.
Serving, walking, and other modes refuse Git sources without acquiring; https and ssh
stay closed; acquired content is not served.

Still open:

1. **Whether `--show` recurses into containers.** Carried forward from the parity plan,
   unresolved, and not on the critical path.

## References

- [CLI parity and golden coverage](../done/plan-2026-08-21-cli-parity-and-golden-coverage.md)
- [Git status and working-tree diffs](plan-2026-08-26-git-status-and-working-tree-diffs.md)
- [Repository library and open from a Git URL](plan-2026-08-11-open-repo-from-git-url.md)
- [Hosted review model and GitHub provider](plan-2026-08-27-github-provider-and-pull-requests.md)
- [Delivery order review](../../reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md)
- [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)
- `tbd guidelines golden-testing-guidelines`

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
