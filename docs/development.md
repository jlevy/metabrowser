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
- New renderer state must have an explicit disposal path.
- Colors come from design tokens.
- Large collections need lazy mounting, virtualization, or a bounded display.
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

The repository uses tbd v0.4.0 for git-native issues and plans:

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
[supply-chain security](../SUPPLY-CHAIN-SECURITY.md) for the reviewed version and the
rationale. Two things make an upgrade more than an `npm install -g`. Node version
managers keep a separate global package tree per Node version, so install the same
release into every Node version used with this repository — at minimum the manager’s
default and the version pinned in `.node-version`. A stale copy under another Node
version silently reverts caches and forked documents written by the newer one.
`tbd setup --auto` also rewrites files this repository hardens deliberately:
root-anchored hook commands, the exact pinned version in the agent skill files, the
graceful unsupported-platform skip in the GitHub CLI helper, and the cool-off exemption
passed to the pinned fallback invocations.
Re-apply those after running setup and bump the version in
`tests/test_public_hygiene.py`, which enforces them.
Prefer upstream documents over local forks; unfork one once upstream covers the same
guidance.

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
