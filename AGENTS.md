# Agent Instructions

Start with [development](docs/development.md),
[supply-chain security](SUPPLY-CHAIN-SECURITY.md), and the documentation relevant to the
change.

## Build and Test

Use the repository Make targets:

```shell
make install
make format
make lint-check
make test
make verify
```

`make verify` is the required handoff gate.
It includes formatting checks, Python and browser lint, type checks, public-hygiene
checks, tests, locked Python and npm vulnerability audits, distribution inspection, and
isolated installed-wheel smoke tests.
`make install` installs both committed dependency locks.
Run `make hooks-install` once per checkout to install the Lefthook pre-commit and
pre-push gates.

## Python and Dependencies

- Use uv exclusively. Never invoke raw `python` or `pip`, activate `.venv`, or add a
  second environment manager.
- Read [SUPPLY-CHAIN-SECURITY.md](SUPPLY-CHAIN-SECURITY.md) before any dependency or
  tool change.
- Preserve the 14-day cool-off and exact first-party exceptions.
  Commit `uv.lock` and `package-lock.json` when their dependencies change.
- Support the Python range in `pyproject.toml` and add complete annotations to changed
  code.
- Reuse the package’s safe-path, gzip, inventory, projection, and plugin helpers.
- Bound filesystem reads and synchronous work on server request paths.
- Catch only errors the current layer can handle and preserve exception causes.

## Browser and Plugin Boundary

- Keep MetaBrowser core consumer-agnostic.
  Domain schemas, routes, renderers, tests, and styles belong in downstream plugins.
- Plugins use the documented `window.metabrowser` SDK. Do not reach into private
  `app.js` globals.
- Give new renderer state a disposal path and test lazy mounting and replacement.
- Use design tokens instead of local color literals in core components.
- Run Biome and TypeScript check-JS through the Make targets for browser changes.
- Keep new browser modules under the fully strict `tsconfig.json` gate.
  Do not expand the explicit legacy allowlist without a documented reason.

## Documentation and Public Hygiene

- Follow the common document guidelines footer used throughout the repository.
- Format all human-authored Markdown with Flowmark through `make format`.
- Link to source documentation instead of duplicating long policy text.
- Never add credentials, private organization or repository names, private issue IDs,
  personal absolute paths, customer data, or copied operational artifacts.
- Run `uv run --frozen python devtools/public_hygiene.py` before every public release or
  repository-visibility change.

## Git

Keep changes focused and preserve unrelated work.
Before handoff: review the diff, run `make verify`, update and close the relevant tbd
issues, run `tbd sync`, commit, push, open or update the pull request, and watch CI to
completion.

<!-- BEGIN TBD INTEGRATION format=f06 surface=agents-md -->
## tbd

This repository uses **tbd** for git-native issue tracking (beads), spec-driven
planning, and on-demand engineering guidelines.
As the agent, you operate tbd on the user’s behalf: translate their requests into tbd
actions rather than telling them to run commands.

- Run `tbd prime` to load current project state and the full tbd workflow.
- Run `tbd skill` for the complete reusable tbd skill instructions.
- Run `tbd shortcut --list` and `tbd guidelines --list` for on-demand resources.
- Track all work as beads: `tbd create`, `tbd ready`, `tbd close`, and `tbd sync`.

<!-- END TBD INTEGRATION -->

## Cursor Cloud specific instructions

The VM snapshot already has the pinned toolchain installed: uv (in `~/.local/bin`) and
Node 24.18.0 (via nvm).
Login shells get both on `PATH` (configured in `~/.bashrc`), but a bare non-login shell
resolves an injected Node 22 at `/exec-daemon/node`, which breaks `npm ci` with
`EBADENGINE`. The startup update script refreshes dependencies with an explicit `PATH`,
so no manual bootstrap is needed.

Build/test/run commands are documented in [development](docs/development.md); use the
Make targets (`make install`, `make lint-check`, `make test`, `make verify`).
Non-obvious caveats:

- The `metab` CLI is only installed inside `.venv`, not on `PATH`. Run it as
  `uv run --frozen metab ...` (e.g.
  `uv run --frozen metab serve ./tests/manual-fixtures --no-open`). It binds
  `127.0.0.1:8411` by default.
- On this overlay filesystem the file watcher logs `unrecognized fs type 'overlay'` and
  falls back to polling.
  This is expected and harmless.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
