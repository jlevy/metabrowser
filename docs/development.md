# Development

Metabrowser uses uv for Python environments and dependency resolution.
The repository checks Python with Ruff and BasedPyright, browser assets with Biome and
TypeScript check-JS, Markdown with Flowmark, and behavior with pytest, tryscript CLI
goldens, and Node contract tests.
[AGENTS.md](../AGENTS.md) holds the rules every change follows; this guide says how to
work within them and why they are what they are.

## Set Up

Install uv at the version `required-version` in `uv.toml` names, using the
[official uv instructions](https://docs.astral.sh/uv/getting-started/installation/).
Install the Node release `.nvmrc` and `.node-version` pin, with an npm in the range
`engines` in `package.json` gives, and select it with `fnm use`, `nvm use`, or
`mise install`; `npm ci` refuses an older Node with an `EBADENGINE` error.
The tests also need Git and jq on `PATH`, and stop when Node, Git, or jq is missing
([Running Tests](e2e-testing.md#running-tests)). Then clone the repository and run:

```shell
make install
make hooks-install
```

`make install` installs the exact Python and JavaScript dependency locks with
`uv --config-file uv.toml sync --locked` and `npm ci`. `--locked` also asserts that
`uv.lock` matches `pyproject.toml` and `uv.toml`, so a stale or locally contaminated
lock fails at install instead of shipping.
`make hooks-install` installs the Lefthook pre-commit and pre-push gates once per
checkout.

Never activate `.venv` or invoke `python` or `pip` directly.
A machine-global uv configuration such as `~/.config/uv/uv.toml` merges into a bare `uv`
invocation and can rewrite the `[options]` block of `uv.lock`, so the Make targets pass
`--config-file` explicitly.
Outside Make, run `uv --config-file uv.toml run --frozen ...`, and check
`git diff uv.lock` before committing.

## Everyday Commands

```shell
# Apply Python, JavaScript, CSS, and Markdown formatting.
make format

# Check lint and formatting without changing files.
make lint-check

# Run the default test tier: the parallel, serial, and Chrome tiers, then the goldens.
make test

# Run one of those four, or the parallel tier on fewer workers.
make test-parallel PYTEST_WORKERS=2
make test-serial
make test-chrome SHARD=1/4
make test-goldens

# Run every gate before a pull request or release.
make verify

# Audit the frozen Python and npm dependency graphs.
make audit

# Run one test.
uv --config-file uv.toml run --frozen pytest tests/test_plugin_loader.py::test_classifier_priority_wins

# Run some tryscript goldens, or one from any shell, in the goldens' environment.
make test-goldens GOLDENS='tests/golden/cli-doctor.tryscript.md tests/golden/cli-api-*.tryscript.md'
devtools/tryscript.sh run tests/golden/cli-doctor.tryscript.md

# Regenerate every golden and recorded response fixture after an intended change.
make golden-update

# Regenerate only the transcripts and recorder or driver modules named, in the same order.
make golden-update ONLY='tests/golden/cli-doctor.tryscript.md tests/test_cli_golden.py'

# Exercise the full navigation API scenario in process.
uv --config-file uv.toml run --frozen metab ./tests/manual-fixtures --check-api

# Start the development server with the manual browser corpus.
uv --config-file uv.toml run --frozen metab ./tests/manual-fixtures --no-open
```

[End-to-End Testing](e2e-testing.md) covers the test layers, the four parts of
`make test` and the markers that choose them, the outer tiers (`make test-admitted-git`,
`make test-macos`, and `make test-live-github`), the skips each tier allows, and
`make test-report`, `make ci-report`, and `make shard-weights`. Its
[Transient Output](e2e-testing.md#transient-output) says where a run’s temporary files
live and when they are removed.
`tests/golden/cli-check-api.tryscript.md` pins a normalized transcript of the
`--check-api` sequence against a small fixture.

The quality, test, audit, and build targets install both locked environments first, and
Make keeps the stages ordered under parallel jobs.
`make lint` applies the ordinary auto-fixes and then runs the repository’s own checks
(public hygiene, file-type colors, tooltips, supply chain, CI workflow coverage,
artifact contracts, parity, the macOS app’s contract, goldens, and changelog fragments);
`make lint-check` runs the same checks without changing files, plus the startup-script
budget and a Flowmark check.

### Keeping an Active Preview Current

Before handing off a change for interactive testing, update the development app or
browser preview if it is already running.
Leave it closed if it was closed.

- For the macOS app, quit normally when replacing the
  [development bundle](../apps/macos/README.md#build-test-and-run) so saved folder
  windows can reopen. Select the updated `metab` in Settings, then use **File → Restart
  Server** for any affected window still using an old server.
  Check the app build in **About Metabrowser** and the runtime in **Settings**.
- For a browser preview, restart `metab` from the checkout under test and reload the
  existing tab at the new server’s URL.

Confirm the affected page loads from the restarted server before handing it over.

### The Verify Gate

`make verify` runs `install`, `lint-check`, `test`, `audit`, and `build`, and
[AGENTS.md](../AGENTS.md#build-and-test) makes it the handoff gate.
The build step inspects the wheel and rejects local environments, build trees, and
repository-only metadata, then runs an isolated installed-wheel smoke test of the
`metab` command and the `metabrowser` alias, packaged assets, built-in plugin discovery,
KPress rendering, the in-process navigation API check, and `metab --doctor`. The last
makes the release gate validate the plugin diagnostics a user sees rather than only
importing plugin internals.

## Inventory Providers

The served root’s inventory comes from one provider behind the provider-neutral
contract; only the sealed factory imports a concrete one.
Selecting a provider, its debug report, and running a benchmark against it are in the
[Inventory Provider Contract](project/architecture/arch-inventory-provider.md), and
[Adding a Provider](project/architecture/arch-inventory-provider.md#adding-a-provider)
lists what a new one brings.

## Benchmarking Scan and Serve

The performance tools cover three different stages of a browsing session.
[`explorations/performance-loop/`](../explorations/performance-loop/README.md) is the
measured-improvement loop: one hypothesis per round, measured against the unchanged
build on the same corpus, with the verdict written down either way; its browser half
follows the [Web Performance Framework](web-performance-framework.md).
`devtools/bench_serving.py` is the standing benchmark, which
[Scale Benchmark](scale-benchmark.md) runs at fixed sizes.
An exploration answers a question once; a benchmark defends an answer, and only the
second belongs in a release gate.
The scan and startup scenarios share a generated corpus, built from locked installs
under the gitignored `.bench/`. See
[Building the corpus](../explorations/performance-loop/README.md#building-the-corpus).
For post-load browsing, use the
[transition scenario](../explorations/performance-loop/README.md#transition-navigation-scenario)
with a pinned standalone clone of Metabrowser.
For the cost of external fetching, use the
[provider probes](../explorations/performance-loop/README.md#measuring-external-fetching)
and correlate any provider change with a browser result.

Run `devtools/bench_serving.py` before and after a change to the walker, the derived
index state, or the delivery layer, and record the comparison in the pull request; its
docstring has the commands, why it reports a cold scan, a scan with a client attached,
and three settled rollup rows, and the in-page probe for the client half.

### Measurement Discipline

These rules hold for every timing claim, in either harness and for any engine.

- **Pair the sides.** Take both back to back, on the same machine and corpus size.
  Only the comparison carries over; absolute numbers move with the filesystem, the page
  cache, and whatever else runs.
  A stored `--json` from an earlier session is a weak baseline, and a uniform shift
  across every row is the tell of load rather than change: a real change moves the rows
  its mechanism touches.
- **Counts before times.** A count is the same under any load, on any host, in any
  order, so where two engines walking one corpus differ in a count, that difference is
  the finding. Use wall-clock time to confirm a count-level result, not to discover one.
- **A run that did not finish is not a slower run.** A comparison reads back how much
  work each side did, entries indexed and completion state, and refuses to report when
  they differ.
- **A live tree is not a corpus.** A tree something else is writing changes between
  runs. Real trees are worth measuring for shapes no generator produces; record the load
  and entry count beside the number, and iterate against a synthetic corpus.
- **Deterministic profilers overstate high-call-count functions.** Use such a profile to
  find where, then price the candidates in isolation.
- **Order and warm-up are part of the measurement.** Interleave builds and alternate
  passes. Record product startup work separately from post-warm-up measurement.
  Record any synthetic harness warm-up as part of the regime.
- **Record what was compared:** commit and clean-or-dirty state for each build, and a
  mark on profiled runs so they are never quoted as measurements.

`explorations/performance-loop/scan_bench.py` is the engine bench: an in-process mode
for iterating a per-entry change and an interleaved build-against-build mode, both
enforcing the completeness and equal-work checks above.
`explorations/performance-loop/run.py` owns the performance loop’s gates.
`make verify` checks the harnesses but runs no timing experiment.
The per-entry rule these measure is in the
[Engine Performance Model](engine-performance-model.md).

### Comparing File Navigation Without a Browser

`devtools/bench_navigation.py` runs baseline, candidate, candidate, baseline on one
existing tree, each fresh process completing discovery before it is measured, and
compares warm text reads, ETag revalidation, optional Markdown rendering, and concurrent
inventory traffic without writing to the tree.
Its docstring gives the setup and the agreement checks.
Omit `--baseline-metab` for a single-build survey.
`--api-cases` takes a JSON array of named GET cases.
Use paths from the CLI API golden transcripts, such as the Git history in
[cli-api-git.tryscript.md](../tests/golden/cli-api-git.tryscript.md).
The
[ready-to-run history case](../explorations/performance-loop/cases/commit-history.json)
works on a pinned checkout with at least one commit.

```json
[
  {
    "name": "history",
    "path": "/api/git/log?limit=250",
    "expect": {"is_repo": true},
    "compare": ["commits"],
    "revalidate": true
  }
]
```

```shell
uv --config-file uv.toml run --frozen python -m devtools.bench_navigation \
  --root "$CORPUS" --candidate-metab .venv/bin/metab --api-only \
  --api-cases explorations/performance-loop/cases/commit-history.json \
  --rounds 2 --json "$RESULT"
```

`expect` checks golden-derived field values, and `compare` hashes named fields for
equality across reads and builds.
Both accept dotted object keys.
Include fields that prove the expected subject, scope, and content, and omit
run-specific cursors or timestamps.
`revalidate` asks for a verified HTTP 304 on a route with a stable ETag.
The recorded times cover real HTTP requests through the running server, including
response-body transfer and server phases.
Startup until HTTP and inventory readiness, first requests, and repeated requests are
reported separately.
`--api-only` skips the default inventory, Files, and Recent test traffic after
readiness. Add `--baseline-metab` for the interleaved two-build comparison.
Use `--prepare-api NAME` to time a case in the startup preparation phase before
measuring the first user read.
Set the same preparation for both builds in a code comparison.
Use `--cache-seed DIR` for cases that need previously fetched data, such as a cached PR
record. Each server gets its own copy of that cache before its startup clock starts.
Use a snapshot from an isolated preparation run and keep it fixed across the series.
CLI `--api` golden transcripts provide the semantic contract.
Their timings do not include this HTTP path.
Use the browser transition scenario for paint and visual continuity.

## Dependencies

Read [supply-chain security](../SUPPLY-CHAIN-SECURITY.md) before adding or upgrading a
dependency. Use uv and keep the 14-day cool-off for third-party packages:

```shell
uv --config-file uv.toml add --exclude-newer "14 days" package-name
uv --config-file uv.toml add --dev --exclude-newer "14 days" package-name
uv --config-file uv.toml lock --upgrade-package package-name
```

Commit `uv.lock` with every Python dependency change and `package-lock.json` with every
JavaScript tool change.
`pyproject.toml` declares each direct runtime requirement’s minimum version and
`uv.lock` the resolved graph; run the complete gate after a dependency change.

First-party packages, published from repositories this project controls, are outside the
cool-off, and
[Audited First-Party Exceptions](../SUPPLY-CHAIN-SECURITY.md#audited-first-party-exceptions)
records each selection with its review.
Install and upgrade those the standard way their own documentation describes, and commit
what their setup generates exactly as generated.
For tbd:

```shell
npm install -g get-tbd@latest
tbd setup --auto
```

Fix a defect in tbd’s generated hook configs, session scripts, or skills upstream in its
generator, not here: the next `tbd setup` reverts a local edit, and a test that pins
generated contents turns a routine upgrade into a repair.
Three such defects are known:

- **Hook commands resolve against the working directory.** `.claude/settings.json` and
  `.codex/hooks.json` invoke `bash .claude/...` and `bash .codex/...` unanchored, so a
  session whose working directory is not the repository root runs nothing.
- **The `npx` fallback fails for 14 days after every tbd release**, because the
  generated invocation omits `--min-release-age=0` and `.npmrc` sets a cool-off.
  It is reached only when the local `tbd` CLI is missing or format-incompatible.
- **`ensure-gh-cli.sh` exits non-zero on a platform with no pinned checksum**, so the
  session hook fails there rather than skipping.

Browser libraries are exact-pinned npm dev dependencies, never a CDN:
`make vendor-assets` copies each from the lockfile-verified `node_modules` into
`src/metabrowser/static/vendor/` with its license and a hash manifest, which the suite
checks, so Metabrowser works offline.
To bump one, update its pin in `package.json`, run `npm install` and
`make vendor-assets`, and commit the vendored files with the lock.
KPress is an exact runtime dependency, because its rendering contract is part of the
release surface, so a KPress bump takes the same validation as a source change.

## Deferred Imports

Imports go at the top of a module.
An import inside a function argues for itself, and each kind has a test that holds its
boundary:

- **The KPress runtime**, in `metabrowser/kpress_adapter.py`, and the projection module
  the Markdown child runs, in `metabrowser/diff/markdown_projection_worker.py`, which
  the server imports to manage the child.
  `test_the_server_imports_no_renderer_for_the_child_it_manages` in
  `tests/test_inert_render_deadline.py` holds both.
- **A mode’s own module**, imported in that mode’s branch of the command line, so that
  `--version` and `--help` do not build the application.
  `test_version_command_does_not_load_git_source_or_server_modules` in
  `tests/test_plugin_public_api.py` holds it.
- **What only a Git source needs**: the revision tree source, its routes, acquisition,
  and `--diff`. A folder’s process never opens a repository, so a handler imports them
  behind the subject check (`source.as_git_revision_subject`). The same test module runs
  every mode and every route a folder’s page asks for in a fresh interpreter and fails
  when one of `_GIT_SOURCE_MODULES` is loaded.
  A served pin imports its routes as it starts (`cli/git_pin_cli.py`), so its first
  request does not import them on the event loop.
- **The file-ages service and the version check**, in `GitRevisionSubject.aclose` and
  `GitRevisionSubject.capabilities`: `--present` imports `git/tree_source.py` for
  `GitPath` alone, and they would load Git’s version check, the shallow-boundary reader,
  and the event log with it.
  `test_present_dry_run_loads_little_beyond_version` in
  `tests/test_plugin_public_api.py` holds it.

**Why KPress is deferred.** A CLI’s startup cost is paid on every invocation, by people
waiting and by agents making many calls.
KPress and its rendering stack were the largest single cost of importing
`metabrowser.server`, and only `/api/kpress/render`, `/api/kpress/export`, and
`/kpress-static/*` need them; the shell derives KPress font URLs from package metadata
without loading the renderer.
[exp-028](../explorations/performance-loop/experiments/exp-028-v091-candidate-rejected-on-cold-shell-import.md)
and
[exp-037](../explorations/performance-loop/experiments/exp-037-startup-imports-and-loading-tiers-for-v012.md)
hold the measurements.
Serve is the exception: right after its delayed server import, and before Uvicorn starts
the inventory lifespan, it initializes KPress and resolves the stylesheets every shell
requests, so a render-blocking request does not pay for the import while it competes
with inventory startup.

**What a deferral costs.** It trades a startup cost for a first-call cost, and turns a
missing dependency from an import error into a run-time one.
Annotations are free to defer under `from __future__ import annotations`; anything
called or constructed, as `KPressExportRequest` is, is not.

**The bar for another one** is all three of: the saving is measured, the dependency is
heavy and optional to most callers, and the module keeps a patchable seam.
`kpress_adapter` keeps `_kpress_runtime` as a module attribute for that third reason, so
`monkeypatch.setattr(kpress_adapter, "_kpress_runtime", fake)` still works.
If a deferral cannot meet all three, put the import back at the top.

## CLI and Functional UI Parity

The rule is in [AGENTS.md](../AGENTS.md#cli-and-functional-ui-parity), and the tables
`devtools/check_parity.py` reads are in the
[parity registry](project/architecture/arch-parity-registry.md).
This section is the reasoning behind them.

A selection travels four layers: route, kind, model, and view.
Three of those are data and need no screen.
The view is not one indivisible exemption either: view code mixes deterministic product
behavior with paint and platform behavior, and only the latter needs a browser.

**Model parity is not wire parity.** `--walk` and `--diff` reach their models through
the library, so they prove the model and not the route: a route can accept a parameter
the library never sees, or drop an envelope key, with those transcripts still green.
`--api` closes that gap by issuing the request the browser would issue.
So a golden counts as evidence for a route only when a `$ metab` command names it, or
names a mode that resolves it internally, as `--show` resolves `/api/file` and
`--check-api` resolves `/api/tree`. `--api` is never such a mode, because it always
names its route.
The same check requires each kind a built-in manifest declares to appear
as exact `kind: <id>` output in a golden’s console block; a prose mention does not
count.

**What counts as evidence.** A command is evidence for a route when it exits 0, in a
tryscript transcript or in an in-process `.txt` golden, whose `# command` and `exit:`
lines the check reads the same way; `devtools/check_goldens.py` fails a `.txt` golden no
test compares. In-process goldens exist for commands a subprocess cannot run, such as a
pull-request refresh that needs `gh`, and a tryscript transcript then pins the same
route failing without `gh`. A golden may write into the tryscript sandbox, as
`/api/kpress/export` does, when what it writes is the same on every run.
A command may start with environment assignments, such as
`METABROWSER_CACHE_DIR=$PWD/<home>`, because tryscript frontmatter cannot name the
sandbox path; the check skips those and nothing else.

**State counts too.** The repository cache persists layout, identity, entry state, and
abandoned staging, none of which appears in a response envelope.
Those are read through `/api/cache/*` like any other model rather than through an
inspection command, which is the practical reason to prefer a route to a CLI mode.
`tests/golden/cli-api-cache.tryscript.md` pins them against homes that
`tests/cache_home_fixture.py` builds with the production writers.
`--no-serve`, the one command that writes the cache, runs in process with the
acquisition floor substituted and the clock fixed, because a transcript must pass on
whatever Git the machine has.

**The exempt rows are the honest boundary.** A server-sent-event response has no
terminating envelope, so `--api` bounds the request and fails rather than hanging; that
is behavior worth having, not a model a transcript can assert, and `tests/dom/` and the
event tests cover the content instead.
A covered row can also pin less than the others: `/api/activity` marks a file active
only after two polls, which a one-shot process never reaches, so its transcript pins the
envelope and `tests/test_browser_active_tracker.py` asserts the nonempty case.

**Functional UI parity is about ownership, not simulation.** Route reachability is
necessary and insufficient: a view can combine two correct models incorrectly, such as a
tally that counts the complete response beside folder visibility that depends on the
rows mounted in the DOM. So every user-visible aspect has a tier.
Membership, ordering, counts, bounds, state, actions, and errors are **data**, behind a
route or model and exercised through `metab`. Focus, disclosure, pagination, and
lifecycle may stay in JavaScript as **interaction**, where a browserless session loads
the exact production module and records the composed behavior.
Geometry, animation, real paint timing, and browser APIs are **paint-exempt**, each with
a specific reason and focused evidence.
Do not mirror JavaScript behavior in Python, and do not grow a general fake DOM.

The check makes those tiers executable.
For an interaction row it runs the session under V8 coverage and credits an owner only
when the session executed that production file and one named function in it, so a
transitive import, a stdout claim, or a relabeled snippet is not evidence.
The **Data inputs** column states provenance: a data row declares `owned-route`, or
`owned-model` for the model of a mode no route can honestly serve, such as `--present`,
which must start no server; a paint-exempt row `local-only`, and an interaction row
names registered, parity-covered routes, `local-only`, or `transport-exempt:/api/events`
for the event stream whose snapshot its data routes already own.
The check cannot infer an undeclared behavior from source code, so review requires a row
whenever a change adds or alters an observable contract.

**Why goldens.** `tbd guidelines golden-testing-guidelines` makes the case: capture a
broad, stable slice of what the system does, keep it in the repository, and read the
diffs. The CLI starts the real application in process, so transcripts exercise route,
kind, and model behavior without browser automation, and real-browser tests stay focused
on paint and platform integration.
`make golden-update` records an intended change and is never run to clear a failure: a
regenerated transcript nobody read turns a regression into an expectation.
When a change touches a few transcripts, `make golden-update ONLY='<file>...'` records
those alone, so a golden this machine cannot pass, such as one that needs a newer Git,
is not rewritten with this machine’s failure.

**Normalize only what a fixture cannot pin.** `metabrowser/normalize.py` is the session
schema. Revisions and mtimes stay real, because fixture repositories build
deterministically and fixtures pin mtimes with `touch -t`; hiding a value the fixture
controls removes the coverage the golden exists for.
Placeholders use angle brackets, because tryscript reads `[NAME]` in expected output as
an elision pattern.

## Compatibility and Legacy Code

`tbd guidelines backward-compatibility-rules` owns the general rules.
This section records the facts about this repository and its standing answers.

The deciding question is whether a real consumer cannot update alongside the producer,
or whether a released version wrote data that needs migrating.
For almost everything here, none does, for a structural reason: the server, the browser
shell, and the built-in plugins ship as one artifact from one repository.
A newly loaded page receives the running build’s shell and inlined settings through an
uncached index response and versioned asset URLs.
An already-open tab keeps its loaded JavaScript until it reloads, so reload tabs after
replacing a local server build; that reload boundary is not a separately versioned
client contract. `/api/*` shapes, `window.metabrowser`, `METABROWSER_SETTINGS`, the
plugin manifest, and the built-in plugin interfaces are therefore internal contracts.

**The macOS app is internal too.** For example, it runs the installed `metab` with the
flags in `CLIServeLaunch` and `MetabRequirement.requiredFlags`, asks it what a GitHub
link opens (`PresentDryRun`) and whether its cache holds a repository
(`RepositoryCache`), and reads `GET /api/identity`;
[the app’s contract](project/architecture/arch-app-contract.md) is the whole list.
Metabrowser keeps no compatibility with an older app: change a flag or the route and the
app in the same commit, and raise `MetabRequirement.minimumRelease` when the app needs
the newer `metab`
([the version floor](project/architecture/arch-macos-app.md#the-version-floor)). The
release that carries such a change follows
[Choosing a Version](publishing.md#choosing-a-version).

**The one external artifact** is an exported File Rollup Format packet, which leaves the
repository for another implementation.
It carries a schema version, registry revision, and fingerprint, so a consumer that sees
an unfamiliar identity refuses the payload; follow the format’s Evolution section when
that identity changes, and do not add a second reader for the previous one.

**Plugins are upgraded, not accommodated.** `PLUGIN_SDK_VERSION` in
`plugin_loader/manifest.py` is the contract the host provides; a manifest declaring
anything else is refused at load with a message naming the required version, and
`metab --doctor` reports it.
A manifest that omits `sdk_version` resolves to `_IMPLICIT_PLUGIN_SDK_VERSION`, the
original SDK, a pinned meaning backed by known installed plugins and never the moving
host version. An external plugin updates and declares the new version; the host ships no
shim.

**The user’s data is not a compatibility layer.** Never require a rewrite of the served
tree.
Read persisted browser state defensively, falling back to the default when a stored
value is absent or unusable, and carry a migration only for a key a released version
wrote, which today means none.

### Standing Compatibility Answers

These are this repository’s answers to the template in
`tbd guidelines backward-compatibility-rules`:

| Area | Standing answer | Why |
| --- | --- | --- |
| Internal code | DO NOT MAINTAIN | One repository, one artifact |
| Library APIs | DO NOT MAINTAIN | `window.metabrowser` ships with the shell that uses it |
| Server APIs and the CLI | DO NOT MAINTAIN | `/api/*` and the flags are consumed only by the shell, the macOS app, and the agent skill, all built from this repository; the app’s version floor refuses a `metab` too old for it, and the skill is tested against the `metab` of its own commit and says so |
| Plugin and extension APIs | UPGRADE + GATE | `PLUGIN_SDK_VERSION` refuses a mismatch at load |
| File formats | VERSION + FAIL FAST | Exported packets carry an identity; one reader |
| Persisted client state | DO NOT MAINTAIN | No released version wrote a key needing migration |
| Database schemas | VERSION + FAIL FAST, else REBUILD | The GitHub plugin’s PR catalog is a disposable cache that names its versions: one newer or unreadable is kept and refused with the command that clears it, any other rebuilt; see [the catalog](project/architecture/arch-github-pull-requests.md#the-catalog) |

Raise it with the maintainers if a change needs a different answer, and revisit the
table when the deciding question’s answer changes: a first external plugin author, a
published format, or a client outside this repository.

## Correct by Construction

Prefer a construction that makes a mistake impossible to a test that catches it.
A test that restates what the code says is a second copy of the code: every intended
change must then be made twice, and the test still passes when both copies are wrong the
same way.

- **Single-source a rule the product repeats.** When several surfaces must look or
  behave alike, such as an age’s freshness ink, the order of a pull request’s title,
  stack place, number, and author, or the highlight on a diff’s changed blocks, give
  them one helper, builder, or token, and remove the local overrides that let one
  surface drift. Then nothing per-surface remains to test.
- **Prefer a mechanism that cannot produce the bug.** For example, one background that
  spans each run of changed blocks cannot leave gaps between them, whereas a background
  on each block, corrected with margin fix-ups, can.
- **Test invariants, not the source.** A test should state a property that must hold
  whatever the implementation, such as first paint equals final layout, an address
  round-trips, a count matches its list, or a route’s output survives a restart.
  Avoid tests that only assert a colour, a class name, a CSS value, or an order that the
  code already spells out.
- **Guard the mechanism, not its output.** Where a construction can be bypassed, a cheap
  structural check that every caller uses it (for instance, that no stylesheet colours
  an age except the shared rule) is worth having.
  It enforces one rule, rather than restating each result.
- **Measure, then keep the number with its constant.** Measure layout and performance
  while developing, and record the measurement beside the constant it sets, as
  [Values live in code](../AGENTS.md#documentation-and-public-hygiene) asks.
  Do not turn a measurement into a pixel or colour assertion.

When a change makes an existing test purely duplicative, delete that test in the same
change and say so in the pull request.

## Python

[AGENTS.md](../AGENTS.md#python-and-dependencies) sets the Python rules.
Run Ruff and BasedPyright through `make lint-check`. BasedPyright runs in strict mode
globally; its remaining exceptions are the `executionEnvironments` entries in
`pyproject.toml`, scoped to `src` and `tests`, each naming the diagnostics it
suppresses, while `devtools` gets the unmodified strict floor.
Narrow an entry when a category reaches zero, and never add a broad global suppression.

## Browser Code

Core browser code lives in `src/metabrowser/static/` and built-in renderers in
`src/metabrowser/builtin_plugins/`.
[AGENTS.md](../AGENTS.md#browser-and-plugin-boundary) sets the boundary rules, and
[the browser shell](project/architecture/arch-browser-shell.md) holds the shell’s
modules and the asset loading tiers.

`server.py` and `app.js` are coordination shells: new feature logic belongs in a focused
route, service, store, or renderer module.
Extract existing behavior when a change has contract coverage and a clear boundary, and
do not combine an unrelated rewrite with a release fix.

- Generic source tabs render through `metabrowser.renderSourceView`, and custom source
  renderers emit the language class `langForPath` returns.
  The shell highlights every default or lazily mounted view after its render settles, so
  plugins do not call Highlight.js.
  The registries in `file_extensions.py` and the bound in `settings.py` are injected
  together as the browser’s authority; `test_plugin_sdk_syntax_token_contracts` checks
  every mapping against the vendored grammar registry.
- A message the page shows a reader, whether a notice, an empty state, or an error,
  follows [Reader Messages](design-system-messages.md): one statement and at most one
  remedy, with the detail left in the route’s JSON and the console.
  `tests/test_reader_messages.py` holds what a machine can check of it, in the browser
  scripts and in the server’s answers.
- First-party JavaScript and TypeScript filenames use lowercase kebab-case, because the
  same names appear in imports, manifests, URLs, documents, and test shims.
  Standard dotted roles such as `types.d.ts` are valid, and vendored assets keep their
  upstream names. `make lint-check` enforces it.

`tsconfig.json` applies full strict checking to new browser modules, and
`tsconfig.legacy.json`’s `files` array is the allowlist of older modules that still
permit implicit `any`: a file leaves it once its JSDoc contracts are complete, and none
enters it as a shortcut.
`node_modules/.bin/tsc --noEmit -p tsconfig.legacy.json --noImplicitAny` shows what
remains for a file. Biome runs the recommended rule set over every shipped browser
module, its file-scoped overrides in `biome.json` shrink as files become clean, and
`make lint-check` fails on a Biome warning.

## Documentation

Human-authored Markdown is formatted with the Flowmark release `FLOWMARK_VERSION` in the
`Makefile` pins: run `make format` after editing, and `make lint-check` verifies the
tree. Apply `tbd guidelines common-doc-guidelines` to every human-authored document and
keep its standard footer.

`docs/` holds durable user and contributor guides, indexed by the README’s Documentation
section. `docs/project/`, indexed by its own README, holds project records: architecture
documents under `architecture/`, dated plans the implementation tracks under
`specs/active/`, completed plans under `specs/done/`, research briefs under `research/`,
and QA records under `qa/`. Dated records capture rationale as of their date and receive
addenda rather than rewrites; when a research brief produces decisions the code must
follow, extract them into a plan rather than treating the brief as the contract.

Three conventions apply to every document:

- **Values live in code.** A constant, limit, default, timeout, or enumerated list that
  code defines is documented beside it, in its docstring or comment, with the
  measurement that set it where there is one.
  A document names the constant and the file that holds it and says what it means, but
  does not restate its value.
  The reason is drift: a copied value goes stale the moment the constant changes, and
  nothing fails when it does.
  Restate a value only where a test pins the copy to the code, as `tests/test_keymap.py`
  does for the keyboard table.
- **Describe the present.** Write what is, not what it replaced; Git holds the history.
  Planned work is labeled as planned and links its plan.
- **No tracker IDs in user guides.** Bead IDs and branch names change state without the
  document changing, so they belong in specs, records, `TODO.md`, and architecture
  status lines.

### Agent Skills

Metabrowser’s own skills are named `mb-*` and kept minimal: each routes an agent to the
document that holds the procedure, so the procedure is written once.
They live in `.agents/skills/`, and `.claude/skills/` links to each, so one copy serves
every agent. `mb-add-language` routes to [Adding a Language](adding-a-language.md), and
`mb-add-plugin` to [Plugin Authoring](plugins.md) and
[Adding a File Type](project/architecture/arch-plugin-system.md#adding-a-file-type).
The `metabrowser` skill under `skills/` is different: it ships to users and is installed
by that name. `tbd` and `simple-modern-uv` are installed by their tools, not written
here.

### Architecture Documents

Architecture documents are reference material, so their layout is a convention, and
`tests/test_docs_discipline.py` enforces the parts a machine can hold:

- **Start at the entry point.** [Architecture](architecture.md) maps the layers and
  links every architecture document; each one is also linked from
  `docs/project/README.md`, and the test fails when one is not.
- **State status first.** A `**Status:**` line near the top says whether the document
  describes what exists, what is partly built, or what is only designed.
- **One subject per document, linked rather than repeated.** A fact belongs in one
  document, and duplicated prose diverges silently.
- **A table of registered surfaces names its check.** A document that tabulates what the
  code registers, such as kinds, views, routes, or formats, names the test that compares
  the table to the code; a table nothing checks is worse than none.
- **Update the document in the change that moves the code.** Registering a kind, view,
  route, or format is finished when the documents that list it say so.

### Public Hygiene

`devtools/public_hygiene.py` rejects references to private trees, personal absolute
paths, and other non-public residue, and checks the footer; `make lint-check` runs it on
every change. Run it directly only when changing repository visibility:

```shell
uv --config-file uv.toml run --frozen python devtools/public_hygiene.py
```

What a document must never include is in
[AGENTS.md](../AGENTS.md#documentation-and-public-hygiene).

### Changing This Guidance

[Changing This Guidance](../AGENTS.md#changing-this-guidance) in `AGENTS.md` holds the
rules for adding, checking, and deleting guidance here and there, each with its reason.

## Issue Tracking

The repository uses tbd for git-native issues and plans; `tbd prime` loads the workflow.
`.tbd/config.yml` records the setup version, and `tbd --version` reports the installed
CLI.

```shell
tbd ready
tbd create "Describe the work" --type task
tbd close <issue-id>
tbd sync
```

Track work before changing code, record meaningful dependencies, close issues only after
validation, and run `tbd sync` before the final push.
Node version managers keep a separate global package tree per Node version, so install
the same tbd release into every Node version used here, at least the manager’s default
and the one `.node-version` pins: a stale copy can revert caches and documents the newer
one wrote.

### Linear

Linear shows the project’s efforts, and tbd holds the work inside them.
An effort is a top-level epic: a feature, a body of improvement, or a class of defects
someone would ask about in a status meeting.
The board should hold a few dozen of them; the hundreds of beads beneath them (tasks,
bugs, review findings, single pull requests) stay in tbd.
A per-pull-request mapping was tried first and left 205 linked issues on 2026-11-20, too
many to read as a board.

A bead reaches Linear only when it carries the `linear` label, open or closed
(`integrations.linear.policy` in `.tbd/config.yml`). It also carries one type label,
`Feature`, `Improvement`, or `Bug`, the names of the workspace’s Linear labels, so the
board can be filtered by type.
tbd does not copy the type label yet: give the Linear issue the same label by hand.
`labels.mirror: verbatim` would copy it, but it also copies `linear` and every other
bead label, which Linear does not have and tbd may not create, so every sync retries
them all and goes over tbd’s 40-update guard (2026-11-20; jlevy/tbd#342 asks for a kind
or label mapping).

**Keep the structure as you work:**

- **Every bead in an effort is a descendant of its epic.** Create a bead with
  `--parent`, and move a stray one under the epic it belongs to.
  A one-off fix that belongs to no effort may stay unparented; it has no Linear issue.
- **A new effort is a new top-level epic** with `linear` and a type label, and, when it
  has one, its plan spec (`--spec`). Give it an issue with
  `tbd integration sync --push --bead <epic>`, then set the issue’s type label.
- **Record each pull request or stack on its epic** as well as on its bead:
  `tbd ref add <epic> <pr-url> --kind pr`. One epic can carry many pull requests and
  stacks; a pull request need not map to exactly one issue.
- **An epic is `in_progress` while anything under it is**: a claimed bead, an open pull
  request, or a session working on it.
  When you start work, set the epic’s status too
  (`tbd update <epic> --status in_progress`); when its last active work lands, set it
  back to `open`, or close it when the effort is done.
- **Run `tbd sync`.** It reconciles linked issues in both directions
  (`integrations.on_tbd_sync`), so status, titles, and descriptions follow the beads.

Never run `tbd integration sync --push` without `--bead` for a bead that is already
linked: it overwrites Linear-side edits that a full sync would merge.

## Shared Working Tree

Several agents and worktrees often work this repository at once, so files can appear
modified that the current session never touched.
The Lefthook pre-push gate runs over the working tree, not the commit being pushed, so
another session’s uncommitted file can block a push, and a tree that verifies green can
still push a commit that fails CI.

- Check `git status` before committing and stage only your own hunks.
- Never commit a file you did not write because it shows as modified: half of another
  session’s paired edit passes locally against the newer tree and fails in CI.
- When the gate fails, first check whether the failing file is yours.
- Lefthook cannot run from a worktree created outside the repository, so a clean
  temporary worktree elsewhere is not a way around a dirty one.
- A new worktree has no `node_modules`, and `make lint-check`, `make test`, and
  `make format` run `make install` first every time, which runs `npm ci` and replaces
  `node_modules` even when it is present.
  Copy `node_modules` from a checkout with the same `package-lock.json` (`cp -cR`, a
  cheap clone on APFS) so hooks and `node_modules/.bin` tools work, and run those
  targets as `make -o install lint-check`; never symlink it, because `npm ci` then
  deletes the other checkout’s copy.

Experiment and campaign files follow the
[durable storage](../explorations/performance-loop/README.md#durable-storage) rules.

## Pull Requests

[Git](../AGENTS.md#git) in `AGENTS.md` lists the handoff steps.
Start from current `main` on a focused branch, add the failing test before a regression
fix where practical, keep implementation, documentation, and public-hygiene changes
together when they describe one contract, and review the wheel contents as well as the
diff for unintended files or private residue.

**Changelog entries are fragments.** A change that a user or plugin author can observe
writes its entry as `changelog.d/<bead>.md`, holding the bullets the Unreleased section
would have had, and leaves `CHANGELOG.md` alone.
When every pull request added its entry at the top of Unreleased, each merge to `main`
left every other open pull request with a conflict there, and so a merge-up and a full
CI run; GitHub’s server-side merge ignores the `merge=union` attribute that resolves
such conflicts locally.
`make lint-check` runs `devtools/changelog.py check` against `origin/main`, which
validates the fragments and fails a branch whose Unreleased section gains an entry, and
the [Release Checklist](publishing.md#release-checklist) runs its `assemble`.
[The fragments README](../changelog.d/README.md) has the rules.

**A reference pull request can read as merged.** GitHub marks a pull request merged, and
deletes its branch, as soon as its head commit is reachable from `main`. A reference
branch that keeps removed code, cut at a commit the landing branch also carries, is
therefore “merged” the moment that branch lands, though its code is not on `main` (H89’s
#389 and H90’s #430). Cut a reference branch at a commit the landing branch never
carries, such as a revert of the removal on top of it, or keep a tag.
Cite the preserved code by its commit, never by the pull request’s state.

## Troubleshooting

**`fatal: this operation must be run in a work tree`.** Check `git config core.bare`
first. A subprocess that runs `git init` while a repository-pinning environment variable
is set re-initializes the surrounding repository and writes `core.bare = true` into the
shared configuration.
`GIT_DIR` outranks both the working directory and `git -C`, and git hooks export it from
a linked worktree, so anything a hook-run test suite spawns inherits it; a push from the
primary checkout does not, which is why the failure can look unreproducible.
Repair with `git config core.bare false` from any worktree.
Code that spawns `git` first scrubs the repository-pinning variables,
`_REPO_PINNING_GIT_VARS` in `git/process.py`; the pre-push command in `lefthook.yml` and
`tests/conftest.py` clear the same list, and `tests/test_git_hook_environment.py` checks
both, the goldens that build repositories, and every fixture that runs `git init`.

**`npm` refuses to install.** npm enforces the `before` and `minimum-release-age`
settings and errors when a shell environment sets both.
Pushes run `make install` through the pre-push gate, so this shows as a failing push.
Select the pinned Node first, and unset the conflicting variable for the invocation
rather than weakening the repository’s cool-off.

**A killed `tbd sync` blocks later runs.** It leaves a lock directory under
`.git/tbd/locks/`. Remove it after confirming no tbd process is still running.

## Template Updates

The project was bootstrapped from
[simple-modern-uv](https://github.com/jlevy/simple-modern-uv).
Review template updates as ordinary code changes: keep project-specific tooling, compare
workflow pins, and rerun the full gate.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
