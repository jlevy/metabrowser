# Development

Metabrowser uses uv for Python environments and dependency resolution.
The repository checks Python with Ruff and BasedPyright, browser assets with Biome and
TypeScript check-JS, Markdown with Flowmark, and behavior with pytest, tryscript CLI
goldens, and Node contract tests.

## Set Up

Install uv 0.11.26 or newer using the
[official uv instructions](https://docs.astral.sh/uv/getting-started/installation/),
install Node 24.18.0 or a newer Node 24 release with npm 11.10 or newer, clone the
repository, and run:

```shell
make install
```

This installs the exact Python and JavaScript dependency locks with
`uv --config-file uv.toml sync --locked` and `npm ci`. `--locked` also asserts that
`uv.lock` matches `pyproject.toml` and `uv.toml`, so a stale or locally contaminated
lock fails at install instead of shipping.
The required Node version is pinned in `.node-version` for fnm and mise and in `.nvmrc`
for nvm. Select it with `fnm use`, `nvm use`, or `mise install` before running the Make
targets. `npm ci` refuses to run under an older Node with an `EBADENGINE` error.
Install the repository’s Lefthook git hooks once after setup:

```shell
make hooks-install
```

Do not activate `.venv` or invoke `python` or `pip` directly.
Use `uv --config-file uv.toml run --frozen`, exact-version `uvx`, repository-configured
dependency commands, and the Make targets so commands use the locked environment and
repository supply-chain policy.

A machine-global uv configuration such as `~/.config/uv/uv.toml` merges into direct `uv`
invocations and can silently rewrite the `[options]` block of `uv.lock`. The Make
targets pass `--config-file` explicitly to select the repository `uv.toml`, and
`make install` fails on a contaminated lock.
Pass `--config-file uv.toml` to direct dependency commands outside Make.
After running them, check `git diff uv.lock` before committing and restore the lock if
the options block changed.

## Everyday Commands

```shell
# Apply Python, JavaScript, CSS, and Markdown formatting.
make format

# Check lint and formatting without changing files.
make lint-check

# Run all tests.
make test

# Run every release gate, including the built-wheel smoke test.
make verify

# Audit the frozen Python and npm dependency graphs.
make audit

# Run a targeted test.
uv --config-file uv.toml run --frozen pytest tests/test_plugin_loader.py::test_classifier_priority_wins

# Regenerate the CLI console goldens (tests/golden/) after an intended
# surface change, then review the diff.
make golden-update

# Exercise the full navigation API scenario in-process.
uv --config-file uv.toml run --frozen metab ./tests/manual-fixtures --check-api

# Start the development server with the manual browser corpus.
uv --config-file uv.toml run --frozen metab ./tests/manual-fixtures --no-open
```

The quality, test, audit, and build targets install both locked environments before
running. Make keeps these stages ordered even when invoked with parallel jobs.

`tests/golden/cli-check-api.tryscript.md` pins a normalized transcript of the same
navigation sequence against a small fixture.
A focused concurrency regression test forces inventory mutation at the summary boundary;
the golden then checks that the application lifecycle, routes, response envelopes, and
CLI reporting remain connected.

`make lint` applies the ordinary auto-fixes and then runs supply-chain and
public-hygiene checks.
`make verify` is the handoff standard before a pull request or release.
It also audits both locked dependency graphs.
Its artifact gate rejects local environments, build trees, and repository-only metadata
before an isolated wheel smoke test exercises the installed `metab` command and
`metabrowser` compatibility alias, packaged assets, built-in plugin discovery, KPress
rendering, and the in-process navigation API check.
The installed wheel must also pass `metab --doctor`, so the release gate validates the
user-facing plugin diagnostics rather than only importing plugin internals.

## Asset Loading Tiers

Every browser asset has a loading tier, and the tier is chosen from what the asset costs
rather than from what is convenient to write.
The rule exists because parse and evaluate are paid on load whether or not anything uses
the code: a library in the shell’s eager path costs every reader on every document, and
that cost is invisible in a request count.

**Eager.** A blocking `<script>` in the shell, for code without which the first render
is wrong. This is the core module list in `server.py` and it stays small.

**Prefetched.** Fetched after first paint, during idle, before anything asks.
For code small relative to how likely it is to be wanted, where arriving late would be
visible. A consumer awaits it rather than discovering it missing.

**On demand.** Fetched the first time something needs it, and never otherwise.
For code that is large, narrowly used, or both.

The tier applies to data as well as code.
A bulk payload that only one surface reads follows the same rule as a library that only
one view calls.

### The Lazy Loading Mechanism

The mechanism follows the library’s module format.
Both shapes keep a loaded set and an in-flight promise map, so concurrent callers share
one load and a repeat costs nothing.

**A library that installs a global** loads through `static/asset-loader.js`. The server
publishes named bundles as `window.METABROWSER_ASSET_BUNDLES`, and `ensureAsset(name)`
appends that bundle’s scripts with `async = false` so they run in order — a Chart.js
plugin is inert without `Chart`. `plugin-sdk.js` republishes it as
`metabrowser.ensureAsset`, so a plugin reaches the loader through the documented SDK
rather than a private global.

**An ES module tree** loads through dynamic `import()`, as `loadKpressAssets` in
`plugin-sdk.js` shows: import the module, capture its named export, and hold it.
Two properties keep a vendored ESM tree loadable without a build step.
Its specifiers must be relative, so no import map is needed; and where its filenames
already carry content hashes, only the entry point needs the `?v=` cache-buster that
`_static_asset_url` adds.

A library moved off the eager path needs an absence contract at every consumer: a guard
that today reads “if the global is missing, skip” becomes “await the loader.”
Late arrival must also re-enhance what is already on screen, which is what the
`metabrowser:optional-asset-loaded` event exists for.

### Justifying a Tier

State the measurement, not the intuition.
Take it in a real browser against a real corpus, the way
[rendering large content](large-content-rendering.md) requires for size limits, and
record it with the change.
`devtools/bench_serving.py` covers the serving side; the page-load side is measured the
same way and against the same corpus, so a tier change and a serving change are
comparable.

## Benchmarking Scan and Serve

Two harnesses, and they answer different questions.
[`explorations/performance-loop/`](../explorations/performance-loop/README.md) is the
measured-improvement loop: one hypothesis per round, measured against the unchanged
build on the same corpus, with the verdict written down either way — including when the
answer is no. Its browser half follows the reusable
[Web Performance Framework](web-performance-framework.md): navigation-time observation,
an application adapter, explicit TOML budgets, and invalid-evidence and responsiveness
gates in `record` and `compare`. Nothing there runs in CI. `devtools/bench_serving.py`
below is the standing benchmark.
An exploration answers a question once; a benchmark defends an answer forever, and only
the second earns a place in the release gate.

Both run on one corpus, and it is neither committed nor generated on demand: `.bench/`
is gitignored, so a fresh checkout has none and every command that needs it fails until
it is built. Build it once per machine —
[Building the corpus](../explorations/performance-loop/README.md#building-the-corpus) —
before benchmarking a change or checking a release candidate for regressions.
It is assembled from this repository’s own locked installs, so one commit with one pair
of lockfiles gives one tree and the two builds under comparison face an identical one.

`devtools/bench_serving.py` measures how fast a tree becomes usable and stays usable.
Use it whenever a change touches the walker, the derived index state, or the delivery
layer, and record the comparison in the pull request.

```shell
# Establish a baseline, then measure the change against it.
uv --config-file uv.toml run --frozen python -m devtools.bench_serving \
  --metab /path/to/release/bin/metab \
  --files 100000 --label before --json bench-before.json

uv --config-file uv.toml run --frozen python -m devtools.bench_serving \
  --files 100000 --label after --baseline bench-before.json
```

The corpus, server logs, and result JSON live in `.bench/`, which is not committed.
A corpus is reused when it already matches `--files`, so repeat runs skip the build.
Pass `--metab` on both sides when comparing installed artifacts.
The harness resolves the console script, runs its `--version` command before measuring,
and records both in the result; this prevents `PATH` order from silently changing the
build under test.

Take both sides back to back, on the same machine and the same corpus size.
Only the comparison carries over; the absolute numbers move a great deal with the
filesystem, the page cache, and whatever else is running.
A stored `--json` from an earlier session is a weak baseline for that last reason —
under an unrelated load spike every row of a comparison shifted by 1.2× to 1.8×, which
reads convincingly like a regression and was not one.
A uniform shift across every row is the tell: real changes move the rows their mechanism
touches and leave the rest alone.
Re-measure both sides together before believing any of it.

Three of the reported rows exist because a single blended latency hides what matters.

- The **cold scan** runs with nothing attached and is walker throughput alone.
  It is read from the walker’s own completion record rather than by polling, because
  polling is what the next phase deliberately does.
  A change that leaves this row alone and moves the next one has removed contention, not
  work.
- The **scan with a client attached** is what a reader experiences.
  Rollup work and the walker take CPU from each other, so this is not the cold number.
- The **settled rollup** is reported as three rows, because a real aggregation, a
  retained body, and a `304` revalidation are three different amounts of work.
  Averaging them reports a cache hit rate rather than a latency, and a build with no
  validators shows up as an absent `304` row instead of a fast one.

Tree latency is reported against response size for the same reason: a request that costs
more than a larger response is doing work proportional to something other than its
answer.

The client half is not visible from the server.
`--browser-probe` prints `devtools/bench-browser-probe.js`; load it in an open folder
view and call `await metabrowser.bench.run({clients: 8})`. It reads the `Server-Timing`
header every route already emits, because request count cannot distinguish a shared
computation from a repeated one — N requests are N requests either way, and what differs
is the work the server did.
It reports, per query shape, whether validators are working and what N simultaneous
clients cost, and it separates coalescing from the retained body rather than crediting
one for the other.

## File Rollup Format Maintenance

The [File Rollup Format](project/architecture/file-rollup-format/file-rollup-format.md)
defines the application-independent classification and aggregation contract.
Its
[recommended file-type definitions](project/architecture/file-rollup-format/recommended-file-types.toml)
are a generated documentation copy of the packaged source at
`src/metabrowser/data/file-rollup-format/recommended-file-types.toml`. Edit the packaged
TOML source, not the documentation copy.

For a definitions-only change, increment `registry_revision` in the packaged TOML. Use
the version boundaries in the format’s Evolution section when a change affects the
registry structure, a serialized component, or the overall rollup semantics.
Stable IDs are compatibility keys and must not be reassigned to a different meaning.

Regenerate the documentation copy, projected registry, conformance corpus, and empty
example after changing the definitions or their reference behavior:

```shell
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py --write
```

Review every generated diff, then run the checker without a mode to prove that all
checked artifacts match the source and validate against their JSON Schemas:

```shell
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py
uv --config-file uv.toml run --frozen pytest \
  tests/test_file_type_contract.py \
  tests/test_file_type_registry.py \
  tests/test_file_type_taxonomy_js.py
make verify
```

To hand the format to another implementation, export a self-contained packet into an
explicit destination and record the reviewed source revision:

```shell
uv --config-file uv.toml run --frozen python devtools/file_type_contract.py \
  --export /explicit/destination/file-rollup-format \
  --source-revision SOURCE_GIT_REVISION

uv --config-file uv.toml run --frozen python devtools/file_type_contract.py \
  --verify /explicit/destination/file-rollup-format
```

Export replaces stale packet contents and immediately verifies the result.
The manifest pins the source revision, registry schema and data revisions, normalized
registry fingerprint, exact file list, and SHA-256 digest of every artifact.
Verification rejects unsafe paths, symbolic links, missing or extra content, duplicate
entries, and hash mismatches.
The packet has no network, sibling-repository, or package-import dependency; its format
document, recommended definitions, schemas, conformance cases, and empty example are the
complete adoption boundary.

## Dependencies

Read [supply-chain security](../SUPPLY-CHAIN-SECURITY.md) before adding or upgrading a
dependency. Use uv and retain the 14-day cool-off:

```shell
uv --config-file uv.toml add --exclude-newer "14 days" package-name
uv --config-file uv.toml add --dev --exclude-newer "14 days" package-name
uv --config-file uv.toml lock --upgrade-package package-name
```

Commit `uv.lock` with every Python dependency change and `package-lock.json` with every
JavaScript tool change.
Do not add requirements files, Poetry, or another environment manager.

The cool-off is a control on third-party code, where an upstream publisher could be
compromised without us knowing.
First-party packages — the ones published from repositories this project controls, tbd
among them — are outside it, because that risk is already managed by the process that
releases them. Install and upgrade those the standard way their own documentation
describes:

```shell
npm install -g get-tbd@latest
tbd setup --auto
```

`tbd setup` owns the hook configs, session scripts, and agent skills it writes.
Commit them exactly as generated and commit the diff the upgrade reports.

Three consequences of that are worth knowing rather than rediscovering, since each one
was previously patched locally and is now left as generated:

- **Hook commands resolve against the working directory.** `.claude/settings.json` and
  `.codex/hooks.json` invoke `bash .claude/...` and `bash .codex/...` with no root
  anchoring, so a session whose cwd is not the repository root runs nothing.
- **The `npx` fallback fails for fourteen days after every tbd release**, because the
  generated invocation omits `--min-release-age=0` and `.npmrc` sets a 14-day cool-off.
  It is only reached when the local `tbd` CLI is missing or format-incompatible.
  See
  [supply-chain security](../SUPPLY-CHAIN-SECURITY.md#audited-first-party-exceptions).
- **`ensure-gh-cli.sh` exits non-zero on a platform with no pinned checksum**, so the
  session hook fails there rather than skipping an optional convenience.
  Checksums cover linux and macOS on amd64 and arm64.

Fix any of these upstream in tbd’s generator rather than in this repository, or the next
`tbd setup` reverts the fix and someone has to notice.
Do not hand-patch them and do not add tests that assert their contents: the same upgrade
runs across many repositories, and a local edit is silently reverted by the next one
while a test that pins their contents turns a routine upgrade into a repair job.
This repository learned that twice.

Every direct runtime requirement declares the minimum version covered by the frozen
release graph. `pyproject.toml` owns those requirements, while `uv.lock` records the
resolved graph. Update both through uv and run the complete release gate after a
dependency change.

Third-party browser libraries are not loaded from a CDN. They are exact-pinned npm dev
dependencies vendored into the wheel by `make vendor-assets`, which copies each file out
of the lockfile-verified `node_modules` into `src/metabrowser/static/vendor/` with its
license text and a hash manifest.
The test suite verifies the committed files against the manifest and that the served
page references no external origins, so Metabrowser works offline.
To bump a browser library, update its pin in `package.json`, run `npm install` to
refresh `package-lock.json`, run `make vendor-assets`, and commit the vendored files
with the lock.

Configuration files own their respective tool versions, entry points, lint and type
ratchets, and build behavior.
The verification gate proves those settings by running the locked tools, tests, audits,
build, distribution inspection, and installed-wheel smoke tests.
`devtools/check_supply_chain.py` adds only the cross-file safety checks that those tools
do not provide.

KPress is an exact runtime dependency because its Python and browser rendering contract
is part of the Metabrowser release surface.
Changing the KPress version requires the same rendering, wheel, and public-hygiene
validation as a source change.
KPress 0.3.0 provides the versioned asset-manifest and declarative fragment contracts
used by the browser host.
Metabrowser serves the complete declared closure, treats entry points as authoritative,
honors stylesheet, module, and classic loading modes, and installs any import map before
module entry points.
KPress fragments carry no theme state and omit the standalone resolver by default;
Metabrowser stamps one resolved theme on the root.
The root-level `--kpress-host-font-size-base` hook anchors KPress’s derived type ramp to
Metabrowser’s document scale, while scoped public size tokens express deliberate mono,
secondary-text, and label divergences.

## Deferred Imports

Imports go at the top of a module.
There is one exception, in `metabrowser/kpress_adapter.py`, and it is written down here
so the next one has to argue for itself rather than cite precedent.

**Why that one.** A CLI’s startup cost is a tax on every invocation, paid by humans
waiting and by agents making many calls.
Importing `metabrowser.server` cost about 345 ms, of which KPress and its rendering
stack were the largest single contributor — and only four surfaces need it: the browser
shell’s HTML, `/api/kpress/render`, `/api/kpress/export`, and `/kpress-static/*`. No
data route touches KPress, so every `--api` call was paying for a renderer it never
used. Deferring it took `metab --api` from 451 ms to 364 ms, about 19%.

**What a deferral costs.** It trades a startup cost for a first-call cost, and it turns
a missing dependency from an import error into a run-time one.
Deferring the KPress *models* immediately proved the point: `KPressExportRequest` is
constructed, not merely annotated, and moving it under `TYPE_CHECKING` broke four tests.
Annotations are free to defer under `from __future__ import annotations`; anything
called or constructed is not.

**The bar for another one.** All three of:

1. the saving is *measured*, not assumed;
2. the dependency is heavy and genuinely optional to most callers; and
3. the module keeps a patchable seam, so tests that substitute the dependency still
   work.

`kpress_adapter` keeps `_kpress_runtime` as a module attribute for exactly that third
reason — `monkeypatch.setattr(kpress_adapter, "_kpress_runtime", fake)` behaves as it
did when the import was at the top.

If a deferral cannot meet all three, put the import back at the top and find the time
somewhere else.

## CLI Parity and Goldens

A selection travels four layers — route, kind, model, view.
Three of those are data and need no screen, which is why parity is stated at the model
layer and only the view is exempt.
The rule itself is in [AGENTS.md](../AGENTS.md); the reasoning is here.

**Why a rule rather than a habit.** Two of eleven data surfaces had CLI coverage when
this was written, and the two that did — the tree and the diff — are where this project
had done its hardest debugging.
That is the argument for the rule rather than a coincidence.

**Model parity is not wire parity.** `--walk` and `--diff` reach their models through
the library, so they prove the model and not the route.
A route can accept a parameter the library never sees, or drop an envelope key, with
those transcripts still green — which is what happened when the nav filter shipped.
`--api` closes that gap by issuing the request the browser would issue.
So a golden counts as evidence only if it exercises the route: either a `$ metab`
command names it, or the row names a mode that resolves it internally, which is how
`--show` stands for `/api/file` without spelling it.
`check_parity.py` enforces that distinction, and `--api` is deliberately not such a
mode, because it always names its route.

**Why goldens rather than more integration tests.**
`tbd guidelines golden-testing-guidelines` makes the case: capture a broad, stable slice
of what the system does, keep it in the repository, and read the diffs.
The discipline that keeps it honest is that `make golden-update` records an *intended*
change and is never run to clear a failure.
A regenerated transcript nobody read converts a regression into a committed expectation.

**Normalize only what a fixture cannot pin.** `metabrowser/normalize.py` is the stated
session schema. Revisions and mtimes stay real, because fixture repositories build
deterministically and fixtures pin mtimes with `touch -t`; hiding a value the fixture
controls removes the coverage the golden existed to provide.
Placeholders use angle brackets, because tryscript reads `[NAME]` in expected output as
an elision pattern and `[ROOT]` is one of its built-ins.

**State counts too.** The cache will persist layout, identity, entry state, quarantine,
and trash, none of which appears in a response envelope.
The plan is that those be read through `/api/cache/*` like any other model rather than
through a bespoke inspection command, which is the practical reason to prefer a route to
a CLI mode. Neither the cache nor those routes exists yet; see
[CLI-first delivery](project/specs/active/plan-2026-08-28-cli-first-delivery-map.md).

## Compatibility and Legacy Code

`tbd guidelines backward-compatibility-rules` owns the general rules: the deciding
question, what does not count as a consumer, why versioning is not backward
compatibility, and why an unreachable compatibility layer is worse than unused code.
Read it rather than the summary that used to live here.
This section records only what that guideline cannot know — the facts about this
repository, and the standing answers it asks each project to record once.

**Speculative compatibility layers are forbidden.** The deciding question is whether a
real consumer cannot update alongside the producer, or whether a released version wrote
data that needs migrating.
For almost everything here, none does, and the reason is structural rather than
stylistic.

Metabrowser ships the server, the browser shell, and the built-in plugins as one
artifact from one repository.
The page is served uncached and every asset URL carries a content-derived version, so a
browser cannot hold an old `app.js` against a new `/api/rollup`. Settings are inlined
into that same page, so the browser’s file-type definitions and the server’s are always
the same object from the same process.
There is no window in which the two halves disagree, so code written to survive that
window is dead on arrival.

`/api/*` shapes, `window.metabrowser`, `METABROWSER_SETTINGS`, the plugin manifest, and
the built-in plugin interfaces are therefore internal contracts.
Change one everywhere in one commit, and record it in `CHANGELOG.md` when the change is
observable to someone using Metabrowser or writing a plugin.

**The one genuinely external artifact** is an exported File Rollup Format packet, which
leaves the repository for another implementation.
It carries a schema version, registry revision, and fingerprint so a consumer that sees
an unfamiliar identity refuses the payload rather than guessing.
Follow the format’s Evolution section when that identity changes, and do not add a
second reader for the previous one.

**Plugins are upgraded, not accommodated.** `PLUGIN_SDK_VERSION` in
`plugin_loader/manifest.py` is the contract the host provides; a manifest declaring
anything else is refused at load time with a message naming the required version, and
`metab --doctor` reports it.
Bare manifests accepted by Metabrowser 0.4.0 resolve to the original SDK `0.1`, a pinned
meaning backed by known installed plugins; omission never follows the moving host
version.
Bump that constant only when the contract actually breaks, update every built-in
manifest in the same commit, and note the break in `CHANGELOG.md`. An external plugin
updates and declares the new version; the host ships no shim for the older surface.

**The user’s own data is not a compatibility layer.** Never require a rewrite of the
served tree — those files belong to the user.
Read persisted browser state defensively, falling back to the default when a stored
value is absent or unusable, and carry a migration only for a key some released version
actually wrote, which today means none.

### Standing Compatibility Answers

These are this repository’s answers to the template in
`tbd guidelines backward-compatibility-rules`, recorded once so no change has to ask
again:

| Area | Standing answer | Why |
| --- | --- | --- |
| Internal code | DO NOT MAINTAIN | One repository, one artifact |
| Library APIs | DO NOT MAINTAIN | `window.metabrowser` ships with the shell that uses it |
| Server APIs | DO NOT MAINTAIN | `/api/*` is consumed only by the co-shipped client |
| Plugin and extension APIs | UPGRADE + GATE | `PLUGIN_SDK_VERSION` refuses a mismatch at load |
| File formats | VERSION + FAIL FAST | Exported packets carry an identity; one reader |
| Persisted client state | DO NOT MAINTAIN | No released version wrote a key needing migration |
| Database schemas | N/A | Metabrowser has none |

Raise it with the maintainers if a change needs a different answer; do not assume a
stricter one and build the layer anyway.
Revisit the table when the deciding question’s answer changes — a first external plugin
author, a published format, a client that starts shipping separately.

## Python

- Support the Python range declared in `pyproject.toml`.
- Add complete type annotations to new or changed functions.
- Prefer small typed values and explicit error boundaries over unstructured mappings.
- Catch only errors the current layer can handle; preserve causes with `raise ... from`.
- Keep filesystem and parsing work bounded, especially on request and event-loop paths.
- Use existing safe-path, compression, manifest, and inventory helpers instead of
  creating parallel implementations.

Run Ruff and BasedPyright through `make lint-check` before handoff.
BasedPyright runs in strict mode globally.
Its remaining exceptions are the `executionEnvironments` entries in `pyproject.toml`,
scoped separately to `src` and `tests`; `devtools` receives the unmodified strict floor.
Each entry names the diagnostics it suppresses, so `pyproject.toml` is the current
statement of that debt.
Narrow an entry when a category reaches zero, and never add a broad global suppression.

## Browser Code

Core browser code lives in `src/metabrowser/static/`; built-in renderers live in
`src/metabrowser/builtin_plugins/`.

`server.py` and `app.js` remain compatibility coordination shells for the initial
release. New feature logic belongs in focused route, service, store, or renderer modules
rather than expanding those files.
Extract existing behavior when a change has contract coverage and a clear boundary; do
not combine an unrelated rewrite with a release fix.

- Plugins use `window.metabrowser`, not private variables in `app.js`.
- Generic source tabs render through `metabrowser.renderSourceView`; custom source
  renderers emit the language class returned by `langForPath`. The shell enhances every
  default or lazy-mounted view after its render settles and after first paint, so
  plugins do not call Highlight.js directly.
  The extension and basename registries in `file_extensions.py` and the measured bound
  in `settings.py` are injected together as the browser authority.
  `test_plugin_sdk_syntax_token_contracts` checks every mapping against the vendored
  grammar registry, and `test_syntax_language_extensions_are_always_browser_text` checks
  that every mapped extension reaches a Source view at any file size.
- New renderer state must have an explicit disposal path.
- Colors come from design tokens.
- Large collections need lazy mounting, virtualization, or a bounded display.
- First-party JavaScript and TypeScript filenames use lowercase kebab-case because the
  same names appear in imports, manifests, URLs, documentation, and test shims.
  Standard dotted roles such as `types.d.ts` remain valid, and vendored assets retain
  their upstream names.
  `make lint-check` enforces the rule for tracked and newly added files.
- Run Biome and TypeScript check-JS through the Make targets.

`tsconfig.json` applies full strict checking, including `noImplicitAny`, to new browser
modules automatically.
`tsconfig.legacy.json` is an explicit allowlist of older modules that still permit
implicit `any` while retaining strict null and other strict checks.
Its `files` array is the allowlist; read it there rather than from a count in prose.
No new file may enter it as an ordinary implementation shortcut, and a file leaves it
once its JSDoc contracts are complete.
To see the work remaining for a file, run
`npx --no-install tsc --noEmit -p tsconfig.legacy.json --noImplicitAny`.

Biome checks every shipped browser module, including the legacy application shell, with
the recommended rule set.
Its overrides are file-scoped and listed in `biome.json`. Shrink each override list as
those files become clean.
`make lint-check` treats Biome warnings as failures, so a recommended-rule regression
cannot hide in otherwise green output.
Globals invoked from generated HTML retain their public names through narrow inline
suppressions because those call sites are not visible to static analysis.
All Biome and TypeScript commands run from `package-lock.json` with `npx --no-install`,
so quality checks cannot fetch tools at runtime.

## Documentation

Human-authored Markdown is formatted with the exact Flowmark release pinned in the
Makefile. Run `make format` after editing docs and `make lint-check` to verify the tree
without modifications.
Apply `tbd guidelines common-doc-guidelines` to the README, guidance, specifications,
and other human-authored documents; retain the standard footer.

Documentation is organized by lifecycle.
`docs/` holds durable user and contributor guides.
`docs/project/`, indexed by its own README, holds project design and planning records:
maintained architecture documents under `architecture/`, dated feature plans the
implementation must track under `specs/active/`, completed plans under `specs/done/`,
and dated research briefs under `research/`. Dated records capture rationale as of their
date and receive addenda rather than rewrites; when a research brief produces decisions
the code must follow, extract them into a plan under `specs/active/` instead of treating
the brief as the contract.

### Architecture Documents

Architecture documents are reference material, so their layout is a convention rather
than a preference, and the parts a machine can hold are enforced by
`tests/test_docs_discipline.py`:

- **Start with the map.**
  [Views, models, and routes](project/architecture/arch-views-models-routes.md) is the
  index of what the browser shows, from what, and at what address; every architecture
  document is reachable from it or from `docs/project/README.md`, and the test fails
  when one is not.
- **State status first.** A `**Status:**` line near the top says whether the document
  describes what exists, what is partly built, or what is only designed.
  It is the first thing a reader needs and the first thing to go stale.
- **One subject per document, linked rather than repeated.** A fact belongs in exactly
  one document; everywhere else links to it.
  Duplicated prose is duplicated maintenance, and the copies diverge silently.
- **A table of registered surfaces names its check.** A document that tabulates what the
  code registers — kinds, views, routes, formats — must name the test that compares the
  table to the code, so a reader knows the table is enforced rather than hopeful.
  A table nothing checks is worse than no table.
- **Update the document in the change that moves the code.** Registering a kind, view,
  route, or format is not finished until the map and any affected document say so; the
  tests above make that a gate rather than a habit.

The public-hygiene gate rejects references to the private guidance tree and other
non-public residue; see `devtools/public_hygiene.py` for the enforced rules.
`make lint-check` runs it on every change, so a release needs no separate pass.
Run it directly only when changing repository visibility, which the ordinary gate never
sees:

```shell
uv --config-file uv.toml run --frozen python devtools/public_hygiene.py
```

Keep documentation public-safe.
Do not include private repository names, internal issue identifiers, personal absolute
paths, credentials, customer data, or copied operational files.

### Changing This Guidance

This document and `AGENTS.md` constrain everyone who works here, so a rule has to earn
its place the same way code does.

- State the reason with the rule.
  A reader who cannot reconstruct why a rule exists cannot tell when it stops applying,
  and will either cargo-cult it or quietly ignore it.
- Prefer a check over a sentence.
  Anything a linter, type checker, test, or Make target can enforce belongs there
  instead; guidance that restates what `make verify` already enforces only adds a second
  place to drift.
- Do not put numbers in prose that nothing maintains.
  Hand-typed counts and baselines rot silently and then mislead — cite the file or the
  command that reports the current value.
- Delete a rule whose reason no longer holds.
  Guidance is not append-only, and a stale restriction costs more than the absent rule
  would.

Challenging an existing rule from first principles is ordinary work, not an overstep.

## Issue Tracking

The repository uses tbd v0.8.1 for git-native issues and plans:

```shell
tbd prime
tbd ready
tbd create "Describe the work" --type task
tbd close <issue-id>
tbd sync
```

Track implementation work before changing code, record meaningful dependencies, and
close issues only after validation.
Run `tbd sync` before the final push.

The tracker is a first-party package with an audited cool-off exception; see
[supply-chain security](../SUPPLY-CHAIN-SECURITY.md) for the rationale.
Node version managers keep a separate global package tree per Node version, so install
the same release into every Node version used with this repository—at minimum the
manager’s default and the version pinned in `.node-version`. A stale copy under another
Node version can silently revert caches and forked documents written by the newer one.
After upgrading, run `tbd setup --auto` and commit its generated hook configs, session
scripts, skills, and configuration exactly as generated.
Fix generator defects upstream rather than hand-patching outputs that the next setup run
will replace.

## Shared Working Tree

This repository is commonly worked by several agents and worktrees at once, so files can
appear modified mid-session that the current session never touched.
The Lefthook pre-push gate compounds this: it runs the quality and test targets over the
**working tree**, not over the commit being pushed.
Another session’s uncommitted file can therefore block an unrelated push, and a tree
that verifies green can still push a commit that fails CI.

- Check `git status` before committing and stage only your own hunks.
- Never commit a file you did not write merely because it shows as modified.
  Half of another session’s paired edit — a test without the change it covers — passes
  locally against the newer tree and fails in CI.
- When the gate fails, first check whether the offending file is yours.
  A failure in another session’s work is something to raise, not to silently fix.
- Lefthook cannot run from a git worktree created outside the repository, so pushing
  from a clean temporary worktree is not a workaround for a dirty one.

## Pull Requests

1. Start from current `main` and create a focused branch.
2. Add or update the failing test before a regression fix where practical.
3. Keep implementation, documentation, and public-hygiene changes together when they
   describe one contract.
4. Run `make verify`.
5. Review the diff and wheel contents for unintended files or private residue.
6. Commit, push, open the pull request, and watch CI to completion.

## Troubleshooting

**`fatal: this operation must be run in a work tree`.** Check `git config core.bare`
before suspecting worktree configuration, test pollution, or a concurrent session.
A subprocess that runs `git init` while a repository-pinning environment variable is set
re-initializes the surrounding repository instead of the intended directory, and writes
`core.bare = true` into the shared configuration.
`GIT_DIR` outranks both the working directory and `git -C`, and git hooks export it, so
anything a hook-run test suite spawns inherits it.
Repair with `git config core.bare false` from any worktree; it writes the shared
configuration. The signature is distinctive: the suite passes standalone and fails only
under `git push`, and later unrelated git commands keep failing after the hook exits.
Code that spawns `git` must first scrub the repository-pinning variables — `GIT_DIR`,
`GIT_WORK_TREE`, `GIT_INDEX_FILE`, `GIT_COMMON_DIR`, `GIT_OBJECT_DIRECTORY`,
`GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_PREFIX`, `GIT_NAMESPACE`, and
`GIT_CEILING_DIRECTORIES` — and a test should pin that behavior.

**`npm` refuses to install.** npm 11.10 and newer enforce the `before` and
`minimum-release-age` settings and error when a shell environment sets both.
Pushes run `make install` through the pre-push gate, so this surfaces as a failing push
rather than a failing install.
Select the pinned Node version first, and unset the conflicting environment variable for
the invocation rather than weakening the repository’s cool-off configuration.

**A killed `tbd sync` blocks later runs.** It leaves a lock directory under
`.git/tbd/locks/`. Remove it after confirming no tbd process is still running.

## Template Updates

The project was bootstrapped from
[simple-modern-uv](https://github.com/jlevy/simple-modern-uv).
Review future template updates as ordinary code changes: preserve project-specific
tooling, compare workflow pins, and rerun the full verification gate.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
