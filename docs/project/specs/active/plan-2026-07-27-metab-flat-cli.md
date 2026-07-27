# Feature: Flat Single-Command `metab` CLI

**Date:** 2026-07-27 (last updated 2026-07-27)

**Author:** Metabrowser maintainers

**Status:** Implemented

## Overview

Make serving the default operation of `metab` so `metab .` opens a directory the way
`open .` does on macOS. The `serve`, `walk`, `plugins`, and `remote` subcommands are
replaced by mode flags on a single command.
This is a hard cut with no compatibility aliases: Metabrowser is alpha, and the
subcommand spellings are removed entirely.

## Goals

- `metab ROOT` serves a directory (or file) with no subcommand
- All non-serve operations become flags: `--walk`, `--remote HOST`, `--plugins`,
  `--plugin NAME`, `--doctor`
- Exactly one mode per invocation, with clear usage errors for conflicting mode flags
  and for options that do not apply to the selected mode
- Help output groups options by mode so the flat surface stays readable
- Golden console-output tests cover every mode, help, version, and usage-error surface
- All documentation reflects only the new interface

## Non-Goals

- Compatibility aliases or deprecation shims for the old subcommands
- New serving, walking, plugin, or tunneling behavior; every mode keeps its current
  implementation and options
- A config file or environment-variable redesign

## Background

The first release routed `metab <path>` through an argv rewrite that prepended the
`serve` subcommand, so the bare form worked but `--help` still presented a
subcommand-style CLI (`serve`, `walk`, `plugins list|show|doctor`, `remote`). The
subcommand layer added routing code (`_rewrite_bare_form`, a `plugins` sub-app),
reserved directory names like `serve` from the bare form, and made the most common
operation the least visible one.
A flat, flag-based CLI matches how the tool is actually used: point it at a path.

## Design

### Command Surface

```
metab [ROOT] [OPTIONS]

metab .                                  # serve current directory
metab path/to/file.jsonl                 # serve parent dir, deep-link the file
metab . --walk --format json             # inventory walk, no server
metab --remote my-vm --path /srv/runs    # SSH tunnel to a remote metab
metab --plugins                          # list discovered plugins
metab --plugin markdown                  # one plugin's resolved manifest
metab --doctor                           # validate every plugin
metab --version
metab                                    # no ROOT and no mode: help, exit 0
```

Modes and their options:

| Mode | Selector | ROOT | Mode options |
| --- | --- | --- | --- |
| serve (default) | none | required | `--path`, `--port`, `--host`, `--no-open`, `--plugins-dir`, `--log-level` |
| walk | `--walk` | required | `--format`, `--stream/--all-at-once`, `--path`, `--detail`, `--max-depth`, `--max-files`, `--log-level` |
| remote | `--remote HOST` | rejected | `--path` (required), `--base-port`, `--no-open`, `--ssh-options`, `--gcp`, `--zone`, `--project` |
| plugins | `--plugins` | rejected | `--plugins-dir`, `--json` |
| plugin | `--plugin NAME` | rejected | `--plugins-dir`, `--json` |
| doctor | `--doctor` | rejected | `--plugins-dir`, `--json` |

`--path` stays one flag with mode-dependent meaning: launch selection under the served
root, walk subtree, or remote directory.
`--no-open`, `--plugins-dir`, and `--log-level` likewise apply to every mode where they
are meaningful and are rejected elsewhere.

### Validation

- Mode selectors are mutually exclusive; passing two (for example `--walk --plugins`) is
  a usage error (exit 2).
- ROOT is required for serve and walk and rejected for remote and plugin modes.
- An option explicitly passed on the command line that does not apply to the selected
  mode is a usage error naming both the option and the mode.
  Click’s `ctx.get_parameter_source` distinguishes explicit values from defaults, so
  defaulted options never trigger false rejections.
- Value validation (port ranges, `--format`, `--detail`, `--log-level` choices, walk
  bounds) is unchanged and runs during parsing, before mode resolution.
  A syntactically invalid value is therefore reported as an invalid-value usage error
  even when the option is also inapplicable to the selected mode (for example
  `metab --plugins --port 0` reports the port range, not the mode).
  The mode-naming diagnostic is guaranteed for inapplicable options whose values parse.
  A golden test pins this precedence.

### Components

- `src/metabrowser/cli/main.py` (new): the single-command Typer app, all option
  declarations with `rich_help_panel` groups (`Serve`, `Walk`, `Remote`, `Plugins`),
  mode resolution and applicability validation, broken-pipe handling, and `main()`.
- `src/metabrowser/cli/serve.py`: serve implementation only (`run_serve` as a plain
  function plus its helpers); app construction, argv rewriting, and subcommand
  registration removed.
- `src/metabrowser/cli/walk_cli.py` (new): the walk implementation (`run_walk`, scoped
  logging), moved out of `serve.py`.
- `src/metabrowser/cli/plugins.py`: `plugins_app` sub-app replaced by plain
  `list_plugins`, `show_plugin`, and `doctor_plugins` functions; output unchanged.
- `src/metabrowser/cli/remote.py`: `run_remote` as a plain function.
  The command it runs on the remote host becomes
  `metab <path> --port N --host 127.0.0.1 --no-open`, so local and remote Metabrowser
  installs must both be at least this version.
- `pyproject.toml`: `metab` and `metabrowser` scripts point at
  `metabrowser.cli.main:main`; `python -m metabrowser.server` delegates there too.

### API Changes

None on the server or plugin surface.
The console interface changes as described; the old subcommands no longer parse.

## Implementation Plan

### Phase 1: Flat CLI

- [x] Build `cli/main.py` with mode dispatch and applicability validation; refactor
  `serve.py`, `plugins.py`, `remote.py` into plain implementation functions; update
  entry points and the remote inner command
- [x] Migrate existing CLI tests to the flat syntax
- [x] Add the golden console-output harness and scenarios
- [x] Update all documentation and the changelog

## Testing Strategy

- Existing CLI behavior tests (`test_cli_serve.py`, `test_plugins_cli.py`,
  `test_remote_cli.py`, `test_cli_plugins_dir_merge.py`, and CLI-invoking e2e tests) are
  migrated to the new syntax, keeping their assertions.
- New golden console-output tests, following the console-capture strategy from
  `tbd guidelines golden-testing-guidelines`, using tryscript, the guideline’s
  recommended runner for CLI goldens.
  The scenarios live in `tests/golden/*.tryscript.md` as markdown files of commands with
  expected output and exit codes, run through `make test` and regenerated with
  `make golden-update`. Determinism comes from a pinned environment (`TERM=dumb` for
  ANSI-free 80-column Rich output, `TZ=UTC`, fixture mtimes pinned with `touch -t`) and
  elision patterns for the version string, sandbox paths, and the builtin-plugin
  checkout prefix. Scenarios: help, version, bare invocation, every plugin mode in text
  and JSON, walk in text/json/yaml and streaming forms, and the full usage-error matrix
  (mode conflicts, inapplicable options, missing or invalid ROOT, invalid option
  values).
- The serve banner scenarios stay in pytest (`tests/test_cli_golden.py`) because they
  mock `uvicorn.run` and the port search in-process, which a tryscript subprocess cannot
  do.
- tryscript is a first-party dependency (github.com/jlevy/tryscript), pinned exactly in
  `package.json`; the 0.1.7 release predates the supply-chain cool-off window by months.
- `make verify` is the gate, including the installed-wheel smoke tests that exercise the
  console scripts.

## Rollout Plan

Ships in the 0.2.0 alpha release with a changelog entry spelling out the new command
forms, including that `metab --remote` sessions require matching versions on both hosts.

The agent skill teaches only the flat grammar and pins `uvx metabrowser@0.2.0`, so
merging this change and publishing 0.2.0 form one release transaction.
The publish workflow enforces it: publishing fails when the release tag does not match
the version pinned in the skill, README, and installation guide, and after publishing it
executes the skill’s pinned invocation (`--help` and `--doctor`) against PyPI.

## Open Questions

None.

## References

- `tbd guidelines golden-testing-guidelines`
- [SUPPLY-CHAIN-SECURITY.md](../../../../SUPPLY-CHAIN-SECURITY.md)
- README.md and docs/plugins.md (primary docs to update)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
