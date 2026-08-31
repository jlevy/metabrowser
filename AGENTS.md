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

## CLI Parity

Every route, kind, and model the browser consumes, and every state the system persists,
has a `metab` equivalent and a golden transcript.
Only the view layer is exempt, and its behaviour is pinned in `tests/dom/`.

- Prefer adding a route to adding a CLI mode.
  `--api` reaches every registered route by construction, so a surface exposed as a
  route is inspectable and golden-pinned for free.
- `devtools/check_parity.py` enforces this and names what is missing.
  The table, the exemption list, and their reasons live in
  [Views, Models, and Routes](docs/project/architecture/arch-views-models-routes.md).
- A new route arrives with its parity row and a golden, or the build fails.
  There is no `gap` status: every registered surface is either covered by a transcript
  or exempt with a stated reason.

## Compatibility and Legacy Code

**Speculative compatibility layers are forbidden.** Apply
`tbd guidelines backward-compatibility-rules` for the general rules, and
[Compatibility and Legacy Code](docs/development.md#compatibility-and-legacy-code) for
this repository’s structural facts and standing answers.

- Name the consumer or released data that cannot update alongside the producer, in the
  pull request, or do not add the layer.
- The server, browser shell, and built-in plugins ship as one artifact, so `/api/*`,
  `window.metabrowser`, `METABROWSER_SETTINGS`, and the plugin manifest are internal
  contracts. Change one everywhere in one commit, and note it in `CHANGELOG.md` when a
  user or plugin author can observe the change.
- `PLUGIN_SDK_VERSION` is a hard gate, not a compatibility layer: bump it on a break and
  update every built-in manifest in the same commit.

## Python and Dependencies

- Use uv exclusively. Never invoke raw `python` or `pip`, activate `.venv`, or add a
  second environment manager.
- Read [SUPPLY-CHAIN-SECURITY.md](SUPPLY-CHAIN-SECURITY.md) before any dependency or
  tool change.
- Preserve the 14-day cool-off for third-party packages, where an upstream publisher
  could be compromised without us knowing.
  First-party packages, tbd among them, are outside it and are installed and upgraded
  the standard way their own documentation describes; commit what their setup generates
  without hand-patching it.
  Commit `uv.lock` and `package-lock.json` when their dependencies change.
- Support the Python range in `pyproject.toml` and add complete annotations to changed
  code.
- Reuse the package’s safe-path, gzip, inventory, projection, and plugin helpers.
- Bound filesystem reads and synchronous work on server request paths.
- Catch only errors the current layer can handle and preserve exception causes.

## Browser and Plugin Boundary

- Keep Metabrowser core consumer-agnostic.
  Domain schemas, routes, renderers, tests, and styles belong in downstream plugins.
- Plugins use the documented `window.metabrowser` SDK. Do not reach into private
  `app.js` globals.
- Give new renderer state a disposal path and test lazy mounting and replacement.
- Measure before bounding.
  A size limit is a claim about cost: establish the shape of that cost in a real
  browser, set the limit at a size you measured, and record the measurement beside the
  constant. See [rendering large content](docs/large-content-rendering.md).
- Use design tokens instead of local color literals in core components.
- Run Biome and TypeScript check-JS through the Make targets for browser changes.
- Keep new browser modules under the fully strict `tsconfig.json` gate.
  Do not expand the explicit legacy allowlist without a documented reason.
- Give every browser asset a loading tier — eager, prefetched, or on demand — and pick
  it from measured cost, not from convenience.
  A script in the shell’s eager path is fetched, parsed, and evaluated whether or not
  anything uses it, so a large or narrowly used library does not belong there.
  See [asset loading tiers](docs/development.md#asset-loading-tiers).

## Documentation and Public Hygiene

- Apply `tbd guidelines common-doc-guidelines` to every human-authored document and
  retain the standard footer.
- Format all human-authored Markdown with the exact `flowmark-rs==0.3.2` pin through
  `make format`.
- Link to source documentation instead of duplicating long policy text.
- Architecture documents follow the layout convention in
  [Architecture Documents](docs/development.md#architecture-documents): status first,
  one subject per document, and a named check for any table of registered surfaces.
  Registering a kind, view, route, or format includes updating
  [the map](docs/project/architecture/arch-views-models-routes.md) in the same change.
- Never add credentials, private organization or repository names, private issue IDs,
  personal absolute paths, customer data, or copied operational artifacts.

## Changing This Guidance

Do not add a rule or restriction here or in `docs/development.md` without deciding from
first principles that it is necessary.
See [Changing This Guidance](docs/development.md#changing-this-guidance).

- State the reason with the rule, so a later reader can tell when it stops applying.
- Prefer a check to a sentence: if `make verify` can enforce it, put it there instead of
  restating it as guidance.
- Never write a count or baseline into prose that nothing maintains.
  Cite the file or command that reports the current value.
- Delete a rule whose reason no longer holds, and treat challenging one from first
  principles as ordinary work.

## Git

Keep changes focused and preserve unrelated work.
Before handoff: review the diff, run `make verify`, update and close the relevant tbd
issues, run `tbd sync`, commit, push, open or update the pull request, and watch CI to
completion.

<!-- BEGIN TBD INTEGRATION format=f08 surface=agents-md -->
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

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
