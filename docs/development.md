# Development

MetaBrowser uses uv for Python environments and dependency resolution.
The repository checks Python with Ruff and BasedPyright, browser assets with Biome and
TypeScript check-JS, Markdown with Flowmark, and behavior with pytest and Node contract
tests.

## Set Up

Install uv 0.11.21 or newer using the
[official uv instructions](https://docs.astral.sh/uv/getting-started/installation/),
install Node 24.18.0 or a newer Node 24 release with npm 11.10 or newer, clone the
repository, and run:

```shell
make install
```

This installs the exact Python and JavaScript dependency locks with `uv sync --frozen`
and `npm ci`. Install the repository’s Lefthook git hooks once after setup:

```shell
make hooks-install
```

Do not activate `.venv` or invoke `python` or `pip` directly.
Use `uv run`, `uvx`, `uv add`, and the Make targets so commands use the locked
environment and repository supply-chain policy.

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
uv run pytest tests/test_plugin_loader.py::test_classifier_priority_wins

# Start the development server from this checkout.
uv run metabrowser serve ./tests/fixtures --no-open
```

`make lint` applies the ordinary auto-fixes and then runs policy and public-hygiene
checks. `make verify` is the handoff standard before a pull request or release.
It also audits both locked dependency graphs.
Its artifact gate rejects local environments, build trees, and repository-only metadata
before an isolated wheel smoke test exercises the installed command, packaged assets,
built-in plugin discovery, and KPress rendering.

## Dependencies

Read [supply-chain security](../SUPPLY-CHAIN-SECURITY.md) before adding or upgrading a
dependency. Use uv and retain the 14-day cool-off:

```shell
uv add --exclude-newer "14 days" package-name
uv add --dev --exclude-newer "14 days" package-name
uv lock --upgrade-package package-name
```

Commit `uv.lock` with every Python dependency change and `package-lock.json` with every
JavaScript tool change.
Do not add requirements files, Poetry, or another environment manager.

KPress is an exact runtime dependency because its Python and browser rendering contract
is part of the MetaBrowser release surface.
Changing the KPress version requires the same rendering, wheel, and public-hygiene
validation as a source change.
KPress 0.2.0 provides the versioned asset-manifest contract used by the browser host:
MetaBrowser serves the complete declared closure, emits browser tags only for entry
points, honors stylesheet, module, and classic loading modes, and installs any import
map before module entry points.

## Python

- Support the Python range declared in `pyproject.toml`.
- Add complete type annotations to new or changed functions.
- Prefer small typed values and explicit error boundaries over unstructured mappings.
- Catch only errors the current layer can handle; preserve causes with `raise ... from`.
- Keep filesystem and parsing work bounded, especially on request and event-loop paths.
- Use existing safe-path, gzip, manifest, and inventory helpers instead of creating
  parallel implementations.

Run Ruff and BasedPyright through `make lint-check` before handoff.
BasedPyright runs in strict mode; narrow exceptions in `pyproject.toml` cover documented
dynamic plugin, compatibility, and untyped dependency boundaries.
Do not broaden those exceptions without recording why strict narrowing is impractical.

## Browser Code

Core browser code lives in `src/metabrowser/static/`; built-in renderers live in
`src/metabrowser/builtin_plugins/`.

- Plugins use `window.metabrowser`, not private variables in `app.js`.
- New renderer state must have an explicit disposal path.
- Colors come from design tokens.
- Large collections need lazy mounting, virtualization, or a bounded display.
- Run Biome and TypeScript check-JS through the Make targets.

`tsconfig.json` applies full strict checking, including `noImplicitAny`, to new browser
modules automatically.
`tsconfig.legacy.json` is an explicit allowlist of older modules that still permit
implicit `any` while retaining strict null and other strict checks.
`app.js` is checked under that legacy configuration while its older dynamic shell is
incrementally typed.
Do not add a file to either exception without documenting the reason; remove files from
the legacy list as their JSDoc contracts become complete.

Biome checks every shipped browser module, including the legacy application shell, with
the recommended rule set and only two configuration-level compatibility exceptions for
intentional CSS ordering and legacy inner declarations.
Globals invoked from generated HTML retain their public names through narrow inline
suppressions because those call sites are not visible to static analysis.
All Biome and TypeScript commands run from `package-lock.json` with `npx --no-install`,
so quality checks cannot fetch tools at runtime.

## Documentation

Human-authored Markdown is formatted with the exact Flowmark release pinned in the
Makefile. Run `make format` after editing docs and `make lint-check` to verify the tree
without modifications.

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
