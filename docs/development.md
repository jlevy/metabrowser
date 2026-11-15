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
The tests also need Git on `PATH`, and stop when Node or Git is missing
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

# Run the default test tier.
make test

# Run every gate before a pull request or release.
make verify

# Audit the frozen Python and npm dependency graphs.
make audit

# Run one test.
uv --config-file uv.toml run --frozen pytest tests/test_plugin_loader.py::test_classifier_priority_wins

# Regenerate every golden and recorded response fixture after an intended change.
make golden-update

# Exercise the full navigation API scenario in process.
uv --config-file uv.toml run --frozen metab ./tests/manual-fixtures --check-api

# Start the development server with the manual browser corpus.
uv --config-file uv.toml run --frozen metab ./tests/manual-fixtures --no-open
```

[End-to-End Testing](e2e-testing.md) covers the test layers, the outer tiers
(`make test-admitted-git`, `make test-macos`, and `make test-live-github`), the skips
each tier allows, and `make test-report`. `tests/golden/cli-check-api.tryscript.md` pins
a normalized transcript of the `--check-api` sequence against a small fixture.

The quality, test, audit, and build targets install both locked environments first, and
Make keeps the stages ordered under parallel jobs.
`make lint` applies the ordinary auto-fixes and then runs the repository’s own checks
(public hygiene, file-type colors, tooltips, supply chain, artifact contracts, parity,
and goldens); `make lint-check` runs the same checks without changing files, plus the
startup-script budget and a Flowmark check.

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
[Inventory Provider Contract](project/architecture/arch-inventory-provider.md).

## Benchmarking Scan and Serve

Two harnesses answer different questions.
[`explorations/performance-loop/`](../explorations/performance-loop/README.md) is the
measured-improvement loop: one hypothesis per round, measured against the unchanged
build on the same corpus, with the verdict written down either way.
Its browser half follows the [Web Performance Framework](web-performance-framework.md).
`devtools/bench_serving.py` is the standing benchmark, and
[Scale Benchmark](scale-benchmark.md) records its baseline figures.
An exploration answers a question once; a benchmark defends an answer, and only the
second belongs in a release gate.

Both run on one corpus, built once per machine into the gitignored `.bench/` by
[Building the corpus](../explorations/performance-loop/README.md#building-the-corpus).
It is assembled from this repository’s own locked installs, so one commit gives one tree
and the two builds under comparison face an identical one.

`devtools/bench_serving.py` measures how fast a tree becomes usable and stays usable.
Use it whenever a change touches the walker, the derived index state, or the delivery
layer, and record the comparison in the pull request:

```shell
# Establish a baseline, then measure the change against it.
uv --config-file uv.toml run --frozen python -m devtools.bench_serving \
  --metab /path/to/release/bin/metab \
  --files 100000 --label before --json bench-before.json

uv --config-file uv.toml run --frozen python -m devtools.bench_serving \
  --files 100000 --label after --baseline bench-before.json
```

A corpus is reused when it already matches `--files`, and the corpus, server logs, and
result JSON stay in `.bench/`. Pass `--metab` on both sides when comparing installed
artifacts: the harness resolves the console script and records its `--version` output,
so `PATH` order cannot change the build under test.

Three of the reported rows exist because a single blended latency hides what matters:

- The **cold scan** runs with nothing attached and is walker throughput alone, read from
  the walker’s completion record rather than by polling.
  A change that leaves this row alone and moves the next one removed contention, not
  work.
- The **scan with a client attached** is what a reader experiences, because rollup work
  and the walker take CPU from each other.
- The **settled rollup** is three rows, because a real aggregation, a retained body, and
  a `304` revalidation are three amounts of work.
  A build with no validators shows up as an absent `304` row rather than a fast one.

Tree latency is reported against response size, because a request that costs more than a
larger response does work proportional to something other than its answer.

The client half is not visible from the server.
`--browser-probe` prints `devtools/bench-browser-probe.js`; load it in an open folder
view and call `await metabrowser.bench.run({clients: 8})`. It reads the `Server-Timing`
header every route emits, because a request count cannot tell a shared computation from
a repeated one, and reports per query shape whether validators work and what
simultaneous clients cost.

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
- **Order and warmup are part of the measurement.** Interleave builds and alternate
  passes, so drift is not charged to whichever ran second, and time and discard a warmup
  pass.
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
existing tree, each fresh process completing discovery before it is measured.
It exercises warm text reads, ETag revalidation, optional Markdown rendering, and
concurrent tree, navigation, rollup, and catalog traffic with and without a large Recent
request, and never writes to the served tree.

Install both checkouts with their committed locks and the same explicit Python
interpreter, patch release and free-threading mode included:

```shell
uv --config-file "$BASELINE/uv.toml" sync --project "$BASELINE" \
  --python "$PWD/.venv/bin/python" --all-extras --all-groups --locked
uv --config-file uv.toml run --frozen python -m devtools.bench_navigation \
  --root . --baseline-metab "$BASELINE/.venv/bin/metab" \
  --file docs/engine-performance-model.md \
  --file tests/test_active_tracker_event_loop_stall.py \
  --render-file docs/engine-performance-model.md \
  --rounds 20 --json "$RESULTS/navigation-comparison.json"
```

`$BASELINE` is an independently checked-out baseline, `$RESULTS` a directory outside the
served tree for the JSON and its `.logs`, and file arguments name paths relative to the
served root; `--baseline-paths native` is for a baseline from before canonical path
identities. The tool refuses mismatched Python builds or GIL modes, and records
dependency versions, source hashes, host load, process CPU and RSS, and raw and
summarized latencies; weigh a dependency difference it reports before attributing a
result to code. Leave the tree unchanged and pause tests, installs, and other benchmarks
during the run. The tool reports success only when status, indexed population, text
content, kind and path, catalog membership and extensions, and Recent membership and
counts agree. A file ageing out of the Recent window, or a Recent population above the
provider’s display cap, fails the comparison; inspect the difference before comparing
timings. Finish in a browser for rendering and interaction costs HTTP cannot see.

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

- **The KPress runtime**, in `metabrowser/kpress_adapter.py`.
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
necessary and insufficient: a view can combine two correct models incorrectly, as Recent
did when its tally counted the complete response while its folder visibility depended on
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
The **Data inputs** column states provenance: a data row declares `owned-route`, a
paint-exempt row `local-only`, and an interaction row names registered, parity-covered
routes, `local-only`, or `transport-exempt:/api/events` for the event stream whose
snapshot its data routes already own.
The check cannot infer an undeclared behavior from source code, so review requires a row
whenever a change adds or alters an observable contract.

**Why goldens.** `tbd guidelines golden-testing-guidelines` makes the case: capture a
broad, stable slice of what the system does, keep it in the repository, and read the
diffs. The CLI starts the real application in process, so transcripts exercise route,
kind, and model behavior without browser automation, and real-browser tests stay focused
on paint and platform integration.
`make golden-update` records an intended change and is never run to clear a failure: a
regenerated transcript nobody read turns a regression into an expectation.

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
| Server APIs | DO NOT MAINTAIN | `/api/*` is consumed only by the co-shipped client |
| Plugin and extension APIs | UPGRADE + GATE | `PLUGIN_SDK_VERSION` refuses a mismatch at load |
| File formats | VERSION + FAIL FAST | Exported packets carry an identity; one reader |
| Persisted client state | DO NOT MAINTAIN | No released version wrote a key needing migration |
| Database schemas | VERSION + FAIL FAST, else REBUILD | The GitHub plugin’s PR catalog is a disposable cache that names its versions: one newer or unreadable is kept and refused with the command that clears it, any other rebuilt; see [Lists of pull requests](project/architecture/arch-repository-sources-and-provider-mirrors.md#lists-of-pull-requests) |

Raise it with the maintainers if a change needs a different answer, and revisit the
table when the deciding question’s answer changes: a first external plugin author, a
published format, or a client that ships separately.

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

This document and `AGENTS.md` constrain everyone who works here, so a rule earns its
place the way code does.

- **State the reason with the rule.** A reader who cannot reconstruct why a rule exists
  cannot tell when it stops applying.
- **Prefer a check to a sentence.** Guidance that restates what `make verify` enforces
  adds a second place to drift.
- **Never put a number in prose that nothing maintains.** Cite the file or command that
  reports the current value.
- **Delete a rule whose reason no longer holds.** Guidance is not append-only.

Challenging an existing rule from first principles is ordinary work.

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

Experiment and campaign files follow the
[durable storage](../explorations/performance-loop/README.md#durable-storage) rules.

## Pull Requests

1. Start from current `main` on a focused branch.
2. Add the failing test before a regression fix where practical.
3. Keep implementation, documentation, and public-hygiene changes together when they
   describe one contract.
4. Run `make verify`.
5. Review the diff and wheel contents for unintended files or private residue.
6. Commit, push, open the pull request, and watch CI to completion.

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
