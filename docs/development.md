# Development

Metabrowser uses uv for Python environments and dependency resolution.
The repository checks Python with Ruff and BasedPyright, browser assets with Biome and
TypeScript check-JS, Markdown with Flowmark, and behavior with pytest and Node contract
tests.

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

# Start the development server with the manual browser corpus.
uv --config-file uv.toml run --frozen metab serve ./tests/manual-fixtures --no-open
```

The quality, test, audit, and build targets install both locked environments before
running. Make keeps these stages ordered even when invoked with parallel jobs.

`make lint` applies the ordinary auto-fixes and then runs supply-chain and
public-hygiene checks.
`make verify` is the handoff standard before a pull request or release.
It also audits both locked dependency graphs.
Its artifact gate rejects local environments, build trees, and repository-only metadata
before an isolated wheel smoke test exercises the installed `metab` command and
`metabrowser` compatibility alias, packaged assets, built-in plugin discovery, and
KPress rendering. The installed wheel must also pass `metab plugins doctor`, so the
release gate validates the user-facing plugin diagnostics rather than only importing
plugin internals.

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
KPress 0.2.2 provides the versioned asset-manifest contract used by the browser host:
Metabrowser serves the complete declared closure, emits browser tags only for entry
points, honors stylesheet, module, and classic loading modes, and installs any import
map before module entry points.

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
Its remaining compatibility exceptions are scoped separately to `src` and `tests`;
`devtools` receives the unmodified strict floor.
The 2026-07-16 ratchet baseline is 121 suppressed source diagnostics at dynamic plugin
and cross-module compatibility boundaries and 362 at pytest fixture and monkeypatch
boundaries. Reduce those counts and remove an exception category when it reaches zero.
Never add a broad global suppression.

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
The 2026-07-16 baseline is 10 files, 7,124 JavaScript lines, and 532 diagnostics when
the allowlist is checked with `noImplicitAny` enabled.
`text/index.js` has graduated to the strict project; move each additional file as its
JSDoc contracts become complete.
No new file may enter the legacy configuration as an ordinary implementation shortcut.
An exceptional addition requires a documented architecture reason and an explicit
follow-up; otherwise the allowlist only shrinks as JSDoc contracts become complete.

Biome checks every shipped browser module, including the legacy application shell, with
the recommended rule set.
Its compatibility overrides are file-scoped: 244 legacy inner declarations across
`app.js`, `charts.js`, `perf.js`, `structured/preview.js`, and `structured/tree.js`,
plus 24 descending-specificity findings in `styles.css` at the 2026-07-16 baseline.
Shrink each override list as those files become clean.
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

Documentation has two public trees plus a project-records area.
`docs/` holds durable user and contributor guides, and `docs/specs/` holds normative
plans and contracts the implementation must track.
Dated research briefs and similar point-in-time records live in the project-records tree
next to them; they capture rationale as of their date and receive addenda rather than
rewrites, and the public-hygiene gate intentionally keeps public documents from
referencing that tree by path.
When a research brief produces decisions the code must follow, extract them into a
`docs/specs/` document instead of treating the brief as the contract.

Keep documentation public-safe.
Do not include private repository names, internal issue identifiers, personal absolute
paths, credentials, customer data, or copied run artifacts.

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

## Pull Requests

1. Start from current `main` and create a focused branch.
2. Add or update the failing test before a regression fix where practical.
3. Keep implementation, documentation, and public-hygiene changes together when they
   describe one contract.
4. Run `make verify`.
5. Review the diff and wheel contents for unintended files or private residue.
6. Commit, push, open the pull request, and watch CI to completion.

## Template Updates

The project was bootstrapped from
[simple-modern-uv](https://github.com/jlevy/simple-modern-uv).
Review future template updates as ordinary code changes: preserve project-specific
tooling, compare workflow pins, and rerun the full verification gate.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
