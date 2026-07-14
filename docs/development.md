# Development

MetaBrowser uses uv for Python environments and dependency resolution.
The repository also checks Python with Ruff and BasedPyright, browser assets with Biome
and TypeScript check-JS, Markdown with Flowmark, and behavior with pytest and Node
contract tests.

## Set Up

Install uv using the
[official uv instructions](https://docs.astral.sh/uv/getting-started/installation/),
clone the repository, and run:

```shell
make install
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

# Run a targeted test.
uv run pytest tests/test_plugin_loader.py::test_classifier_priority_wins

# Start the development server from this checkout.
uv run metabrowser serve ./tests/fixtures --no-open
```

`make lint` applies the ordinary auto-fixes and then runs policy and public-hygiene
checks. `make verify` is the handoff standard before a pull request or release.
Its isolated wheel smoke test exercises the installed command, packaged assets, built-in
plugin discovery, and KPress rendering.

## Dependencies

Read [supply-chain security](../SUPPLY-CHAIN-SECURITY.md) before adding or upgrading a
dependency. Use uv and retain the 14-day cool-off:

```shell
uv add --exclude-newer "14 days" package-name
uv add --dev --exclude-newer "14 days" package-name
uv lock --upgrade-package package-name
```

Commit `uv.lock` with every dependency change.
Do not add requirements files, Poetry, or another environment manager.

KPress is an exact runtime dependency because its Python and browser rendering contract
is part of the MetaBrowser release surface.
Changing the KPress version requires the same rendering, wheel, and public-hygiene
validation as a source change.

## Python

- Support the Python range declared in `pyproject.toml`.
- Add complete type annotations to new or changed functions.
- Prefer small typed values and explicit error boundaries over unstructured mappings.
- Catch only errors the current layer can handle; preserve causes with `raise ... from`.
- Keep filesystem and parsing work bounded, especially on request and event-loop paths.
- Use existing safe-path, gzip, manifest, and inventory helpers instead of creating
  parallel implementations.

Run Ruff and BasedPyright through `make lint-check` before handoff.

## Browser Code

Core browser code lives in `src/metabrowser/static/`; built-in renderers live in
`src/metabrowser/builtin_plugins/`.

- Plugins use `window.metabrowser`, not private variables in `app.js`.
- New renderer state must have an explicit disposal path.
- Colors come from design tokens.
- Large collections need lazy mounting, virtualization, or a bounded display.
- Run Biome and TypeScript check-JS through the Make targets.

`app.js` is currently excluded from TypeScript check-JS while its older dynamic code is
incrementally typed.
Do not broaden that exclusion.
New standalone modules and plugin code must pass the check.

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
