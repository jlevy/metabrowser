# Plan: CLI-First Delivery — Parity Foundation, Git Status, and the Repository Cache

**Date:** 2026-08-28

**Author:** Joshua Levy (with LLM assistance)

**Status:** Draft

## Overview

Three workstreams are queued behind each other:
[CLI parity](plan-2026-08-21-cli-parity-and-golden-coverage.md),
[Git status](plan-2026-08-26-git-status-and-working-tree-diffs.md), and the
[repository library](plan-2026-08-11-open-repo-from-git-url.md).
This document sequences them, maps each to files and functions, and states how all of
the backend work is proved end to end without a browser.

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

The [parity plan](plan-2026-08-21-cli-parity-and-golden-coverage.md) states the
principle over the four layers `route → kind → model → view`, and exempts only the view.
That covers read models.
It does not cover **durable state**, which is most of what the cache is.

The cache writes an application home, a layout record, per-entry identity and state
records, locks, staging directories, quarantine, and trash.
None of that appears in a response envelope, so a `--api` transcript proves nothing
about it. The principle needs a second clause:

> **State clause.** Every state the system persists is reachable from `metab` as a
> normalized model and pinned by a golden transcript.
> Cache layout, entry identity, entry state, and reclamation outcomes are read through
> `/api/cache/*` like any other model, not through a bespoke inspection command.

This is why the cache gets read routes in Phase 1A, before anything can be cloned.
The routes are cheap — they project records the format foundation already writes — and
they turn the entire state machine into something a transcript can assert.

## Ordering

Land in this order. Rows 1–3 are strictly serial; rows 4 and 5 are independent of each
other and of the status work, so they can proceed in parallel.

| # | Work | Beads | Gated by |
| --- | --- | --- | --- |
| 1 | Parity mechanism: ASGI client, normalizer, `--api`, `--show` | `mb-8n8l`, `mb-ian3`, `mb-y5wm` | nothing |
| 2 | Parity enforcement and codification | `mb-esht`, `mb-zodq` | 1 |
| 3 | Git-status measurement gate | `mb-r5gn` | nothing (can overlap 1) |
| 4 | Git-status backend, then panel | `mb-u4mf`, `mb-vibn` | 1, 3 |
| 5 | Cache format foundation, then acquisition | `mb-ire2`, `mb-4gnu`, `mb-h51g` | 1 |
| 6 | HTML trust chain | `mb-cun0`, `mb-vib1` | nothing |
| 7 | URL open and serving | `mb-ew38` | 4, 5, 6 |

Row 6 is the
[R1 finding](../../reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md):
serving fetched content is gated on the trust chain, which no plan prioritized.
It depends on nothing here, so it runs alongside rather than extending the schedule.

Rows 1–2 are behavior-preserving.
The proof is that `tests/golden/cli-check-api.tryscript.md` and every other existing
golden are byte-identical after the refactor.
If a transcript moves, the lift changed behavior and the change is wrong.

## Part 0: Parity Mechanism — Module and Function Map

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

async def wait_for_index(client: InProcessClient, *, timeout_s: float) -> bool: ...
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
    home: Path | None          # METABROWSER_HOME, when set
    keep_revisions: bool        # True for deterministic fixture repos

UNSTABLE_FIELDS: Mapping[str, str]   # field name -> placeholder

def normalize_payload(value: Any, ctx: NormalizeContext) -> Any: ...
def normalize_text(text: str, ctx: NormalizeContext) -> str: ...
def describe_schema() -> str:   # renders the table for docs and for the round-trip test
```

The rules, and why each is needed:

| Field or shape | Becomes | Why |
| --- | --- | --- |
| Absolute path under `root` | `<ROOT>/...` | sandbox path varies |
| Absolute path under `home` | `<HOME>/...` | cache home varies |
| `mtime`, `mtime_hash` | `<MTIME>`, **opt-in** | fixtures pin these with `touch -t`; a clone into the cache cannot |
| Pack file names, `.git` internals | omitted | never stable; see below |
| Git revisions | **kept** | fixture repos are built deterministically |

The table is short because it was measured.
Running the same routes twice against two sandbox roots, the only field that varied was
`root`, and no envelope carries an elapsed or duration field — so an `<ELAPSED>` rule
would be speculative and is absent until something needs it.
Mtime normalization is opt-in rather than default for the same reason revisions are
kept: the existing goldens pin mtimes and assert the real values, and normalizing by
default would delete that coverage.

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
    route: str,
    *,
    fmt: Literal["json", "yaml"],
    data: Path | None,
    wait_index: bool,
) -> int: ...
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

Enumerates registered routes from `server.py`, `git/routes.py`, `cache/routes.py`, and
every manifest `[[data_hook]]`; reads the parity table in
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
2 R. N... 100644 100644 100644 2227cddb 2227cddb R100 renamed.txt\0a.txt\0
1 A. N... 000000 100644 100644 00000000 587be6b4 weird name.txt\0
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
class WorkingTreeAdapter(ComparisonAdapter):
    async def describe(self) -> ComparisonSummary: ...
    async def file_patch(self, path: str) -> FilePatch: ...
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
def ensure_home(home: Path) -> None: # creates, writes CACHEDIR.TAG
```

`METABROWSER_HOME` is the hermeticity seam for every cache golden.

### `src/metabrowser/cache/` (new package)

| Module | Responsibility | Key functions |
| --- | --- | --- |
| `layout.py` | `f01` format record, fail-closed on future formats, ordered migrations | `read_layout`, `migrate`, `LAYOUT_FORMAT` |
| `atomic.py` | same-filesystem staging, atomic YAML, home locking | `write_atomic`, `read_yaml`, `home_lock` |
| `records.py` | SoftSchema contracts | `ApplicationConfig/v1`, `CacheLayout/v1`, `RepositoryIdentity/v1`, `RepositoryState/v1` |
| `state.py` | the state machine | `promote`, `quarantine`, `trash`, `entry_state` |
| `reclaim.py` | startup sweep of `staging/` and `trash/` | `reclaim(home)` |
| `identity.py` | Phase 1B-a: conservative identity and collision-safe slug | `source_identity`, `cache_slug` |
| `urls.py` | Phase 1B-a: the safe URL grammar | `parse_git_source` |
| `acquire.py` | Phase 1B-a: clone into staging, publish atomically | `acquire` |
| `routes.py` | the state clause | `/api/cache/layout`, `/entries`, `/entry/{slug}` |

```python
def parse_git_source(raw: str) -> GitSource | None:
    """None means 'not a Git source' — the caller falls through to local path
    resolution. Rejects credentials, query, fragment, option-like input, and
    unsupported transports by raising, so a malformed URL is never silently
    treated as a directory name."""

async def acquire(source: GitSource, *, home: Path, profile: TrustProfile) -> CacheEntry:
    """Clone into staging/ via run_git, then promote atomically. Never publishes a
    partial tree: a failure quarantines the staging directory and leaves any
    previously published entry untouched."""
```

`cache/routes.py` is the part that is easy to skip and should not be.
Three read routes, written in Phase 1A alongside the records they project, are what make
every subsequent cache behavior assertable from a transcript.

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

Verified: two repositories built this way on Git 2.50.1 both produced HEAD
`1e9bc884891152dfb4e0ac2d87c40f5a5b7389a9`. So Git goldens assert **real revisions**,
not `<REV>` placeholders.
A commit that changes shape changes the golden, which is the entire point.
`--initial-branch=main` is required: the default branch name varies by Git version and
is the one genuinely unstable thing in the recipe.

What is *not* stable, and must never be asserted: pack file names, `.git` internal
layout, object counts after gc, and clone wall time.
`cache/routes.py` therefore projects **logical** entry state — identity, format,
publication state, head revision — and never a directory listing.

### Acquisition without a network

`acquire` clones from a local origin repository created in the same sandbox.
This is real `git clone` through the real `run_git`, with no mocking and no forked code
path, which is what the golden guidelines mean by not forking logic for tests.
It also happens to be the honest test: the failure modes that matter — partial clone,
interrupted publish, quarantine, reuse-on-second-open — are all filesystem behavior, not
network behavior.

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

| Stop | Bead | Why it is not an implementation decision |
| --- | --- | --- |
| Adopting SoftSchema | `mb-4gnu` | Needs either the 14-day cool-off or an *Audited First-Party Exceptions* row with a blast-radius statement, reviewed against its predecessor. That is a security judgment, and [SUPPLY-CHAIN-SECURITY.md](../../../../SUPPLY-CHAIN-SECURITY.md) requires it be argued, not assumed. |
| Unbounded `--untracked-files=all` | `mb-r5gn` | The plan says that if a complete status cannot be bounded usefully, the phase returns to design review. Choosing a partial-status policy instead would be redesigning the feature. |
| Any `PLUGIN_SDK_VERSION` bump | any | A hard gate by [AGENTS.md](../../../../AGENTS.md), not a compatibility layer to negotiate. |
| A golden that changes for an unexplained reason | any | Either a regression or a misunderstanding of the spec. Both need a human before the transcript is rewritten. |

Everything else is ordinary work: the budgets from `mb-r5gn` are chosen from recorded
measurements, and the rename-versus-copy question is answered by whether copy detection
measures cheaply enough on the corpus.
Those are decisions with evidence attached, so they get made and recorded rather than
escalated.

### What lands, in order

The first six beads are unattended work with a clear finish line:

| Order | Bead | Done when |
| --- | --- | --- |
| 1 | `mb-8n8l` | `InProcessClient` and `normalize.py` exist; every existing golden byte-identical |
| 2 | `mb-ian3` | `metab . --api '<route>'` reaches every registered route; `cli-api.tryscript.md` green |
| 3 | `mb-y5wm` | `--show` reports route, kind, views, model; `cli-show.tryscript.md` covers one file per built-in kind |
| 4 | `mb-esht` | `check_parity.py` fails on a missing row, a bad command, and an unpinned row; wired into `make lint-check` |
| 5 | `mb-zodq` | The three clauses in `AGENTS.md`, the reasoning in `docs/development.md` |
| 6 | `mb-r5gn` | Measurements recorded; the three decisions written down or the stop above triggered |

After 6, the status and cache tracks run in parallel and neither needs a browser until
`mb-vibn`.

## Open Decisions

**Closed 2026-08-28: local origins are first-class Git sources.** `file://` URLs and
local repository paths are accepted as Git sources under the **untrusted profile**,
documented as mirror and air-gapped support.
The safe URL grammar’s job is rejecting ambiguous and dangerous input — credentials,
query, fragment, option-like strings — not rejecting a transport that is strictly safer
than the ones already allowed.
This keeps acquisition goldens on exactly the production code path; the rejected
alternative, a test-only escape hatch, forks production and test logic, which
`tbd guidelines golden-testing-guidelines` warns against directly.
`cache/urls.py` therefore classifies transport into `https`, `ssh`, and `local`, and
`acquire` binds `local` to the untrusted profile unconditionally.

Still open:

1. **Where acquisition is triggered from.** Everything in `metab` is read-only today,
   and acquisition writes.
   Recommendation: keep it a side effect of `metab <url>`, and add `--no-serve` so a
   golden can acquire and inspect without starting a server.
   No `/api/cache/acquire` write route; the state clause covers reads only.
2. **Whether `--show` recurses into containers.** Carried forward from the parity plan,
   unresolved, and not on the critical path.

## References

- [CLI parity and golden coverage](plan-2026-08-21-cli-parity-and-golden-coverage.md)
- [Git status and working-tree diffs](plan-2026-08-26-git-status-and-working-tree-diffs.md)
- [Repository library and open from a Git URL](plan-2026-08-11-open-repo-from-git-url.md)
- [Delivery order review](../../reviews/review-2026-08-27-delivery-order-for-status-cache-and-providers.md)
  — lands with branch `design/git-status-and-cache-phasing`, which must merge before
  this document’s links resolve
- [Views, Models, and Routes](../../architecture/arch-views-models-routes.md)
- `tbd guidelines golden-testing-guidelines`

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
