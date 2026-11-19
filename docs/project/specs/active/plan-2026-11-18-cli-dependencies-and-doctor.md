# Plan for the App’s Command-Line Dependencies and a Complete Doctor

**Date:** 2026-11-18

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Phase 1 (the versioning contract) is in the pull request that adds this
plan; Phases 2 and 3 are not started.
Bead `mb-bxli` tracks the work.
Phase 2 waits for the GitHub status check (`mb-si2g`,
jlevy/metabrowserjlevy/metabrowser#581), which rewrites the same doctor function and
owns `gh`’s minimum.
[Open Questions](#open-questions) lists the owner’s decisions.

## The Owner’s Words

On 2026-11-18:

> another question for us to review is to be clear about the dependency between metab
> CLI and the native app.
> Let’s figure out what the best way to handle this is.
> Probably it’s just to have a minimum version dependency represented in each native app
> build and then to instruct the user on how to upgrade metab if necessary.
> And same for gh and potentially, in the future, other CLI dependencies
> 
> We should also make sure the doctor command in metab fully covers everything
> necessary, and that it is available from the macOS app.

And later the same day:

> We should also encode some sort of default convention, we are in if we change metab in
> a way that’s incompatible with the front end, then we should create a new minor or
> major release but not a patch release (unless it’s a bugfix), this contract would be
> at the minor release level or above

## Background

### How the App Finds and Checks `metab`

- **The requirement.** `MetabRequirement` in
  `apps/macos/Sources/ShellCore/Setup/MetabVersion.swift` holds `minimumRelease`,
  `requiredFlags` (`--exit-on-eof`, `--present`, `--recent`), `isReleased`, and
  `upgradeCommand`, which is `uv tool install --upgrade 'metabrowser>=<minimum>'`.
- **Finding it.** `RuntimeDiscovery.discover` (`Runtime/RuntimeDiscovery.swift`) tries,
  in order, the saved path, `METABROWSER_METAB`, `~/.local/bin`, uv’s tool bin
  directory, and the Homebrew prefixes, and only then the login shell’s `PATH`. It runs
  a candidate only when no other account can change it (`ExecutableTrust`).
- **Reading the version.** `RuntimeDiscovery.validate` runs
  `metab --exit-on-eof --present --recent --version` in a server’s minimal environment.
  A build that rejects one of the flags is too old whatever its number
  (`rejectsServeFlag`, `MetabRequirement.flagShortfall`).
- **Telling the user.** `SetupGuide` (`Setup/SetupGuide.swift`) shows only the missing
  steps, each with Copy: install uv, install, reinstall, or upgrade `metab`, or, while
  `isReleased` is false, `make install` in a checkout and Choose metab…. Settings
  (`Metabrowser/RuntimeWindow.swift`) shows the runtime, the `git` and `gh` paths, the
  places looked, and Run Doctor.
- **Upgrade instructions** name uv only.
  A `metab` installed with pipx, or a checkout found through `PATH`, gets the uv
  command, which installs a second copy instead of upgrading the one in use.
- **Noticing an upgrade.** `SetupWatch` compares the executable’s fingerprint, and
  `RuntimeUpgrade` offers to restart servers started from the old version.

### How `gh` and `git` Are Found and Checked

- **The app** finds both once, at setup (`RuntimeDiscovery.resolveTools`): the login
  shell’s `PATH`, then Homebrew, and for `git` `/usr/bin/git`. It records only paths
  (`ToolPaths` in `Runtime/Runtime.swift`), puts their directories first on each
  server’s `PATH` (`ChildEnvironment`), and never runs either itself.
  It reads no version of either.
- **`metab` owns `git`’s minimums**, with reasons beside them: `ACQUISITION_MINIMUM` and
  `ACQUISITION_PATCHED_TRACKS` in `src/metabrowser/git/process.py` (the security floor
  for cloning, frozen in `git-version-gates.json`), and `PARTIAL_CLONE_GIT_MINIMUM` in
  `src/metabrowser/checkout_revisions.py`. A Mac with only the Command Line Tools’ Git
  is below the acquisition floor, and nothing says so before a clone fails.
- **`metab` has no numeric `gh` minimum.** `gh_too_old` (`GhFailureState` in
  `builtin_plugins/github/gh.py`) is inferred when `gh` rejects a subcommand.
  jlevy/metabrowser#581 adds `gh_status.py`: one bounded check of the `gh` path,
  version, account, token source, and scopes, with one state and fix, served by
  `metab --doctor`, `--doctor --json` (a top-level `github` object), and
  `POST /api/plugin/github/status`. It still declares no version number.
- **The app’s GitHub failures** (`Folders/GitHubFailure.swift`, from
  jlevy/metabrowser#571) read the state in a failed start’s `Error:` line and show the
  steps with Copy and Retry; its `notSignedIn` and `noGitHubCLI` kinds wait for
  jlevy/metabrowser#581’s states.

### What `metab --doctor` Covers Today

`doctor_plugins` in `src/metabrowser/cli/plugins.py` validates plugin manifests, data
hook imports, `index.js`, kind and view-key collisions, and the packaged cache record
contracts, and exits 1 on any problem.
Its JSON is `ok`, `plugin_count`, and `problems`; jlevy/metabrowser#581 adds `github`.
The installed-wheel smoke test runs it (`devtools/check_distribution.py`). The app’s Run
Doctor runs `metab --doctor` and shows the raw text (`runDoctor` in
`Metabrowser/AppDelegate.swift`). No menu reaches it.

| Area | Today | Gap |
| --- | --- | --- |
| `metab` install and version | `--version` only | Not in the doctor: version, path, install method |
| Python and uv | `requires-python` in `pyproject.toml` | Interpreter path and version not reported |
| `gh` | jlevy/metabrowser#581: path, version, account, scopes | No declared minimum version |
| `git` | Floors in `git/process.py` and `checkout_revisions.py` | Not in the doctor; a low Git shows only when a clone fails |
| Configuration | `configuration_directory` in `home.py`; `config.yml` read by `cache/layout.py` | Readability and privacy not checked |
| Cache and state | `application_cache` and the owner-only checks in `home.py` | Writability, privacy, and free space not checked |
| Plugins | Checked | None |
| Markdown renderer child | `diff/markdown_projection_worker.py` starts it and cools off after failed starts | A broken renderer shows only on a page |
| Browser for serving | `webbrowser.open` in `cli/serve.py` and `cli/remote.py` | Whether one is registered is not checked |
| The macOS app | `--present` checks `APP_INSTALL_LOCATIONS` and `OPENS_URLS_KEY` (`cli/present.py`) | Not in the doctor; the app’s build does not publish its minimum `metab` |
| github.com reachable | jlevy/metabrowser#581’s `network_error` when `gh` runs | Nothing without `gh` |
| Recent targets | `recent_targets.py` (`STORE_FILE`, format history) | A damaged or newer-format file is not reported |
| Lock files | `cache/locks.py` (`flock`, released when a holder dies) | A fetch lock held by a live refresh is not reported |

Other ways a setup breaks, which the checks below should name:

- **Two `metab`s.** The app’s and Terminal’s differ (a checkout first on `PATH`, a pipx
  and a uv install), and the user upgrades the one the app does not run.
- **A stale editable install.** A checkout’s version comes from install-time metadata
  (`build_version.py`), so a checkout not reinstalled after a pull reports an old
  number.
- **Configuration overrides.** `METABROWSER_CACHE_DIR` or `METABROWSER_CONFIG_DIR` set
  in Terminal and not for the app, or the reverse.
- **A full disk** stops a clone partway, which reads as a network failure.
- **Folder privacy prompts** that macOS raised for the app and the user denied.

## Design

### A Minimum Lives with the Program That Runs the Tool

Each command-line tool has one declared minimum, in one place: the program that runs it.

- **`metab`: the app.** The app runs `metab`, so the app’s build declares its minimum
  (`MetabRequirement`). This is what the owner proposed and what exists.
- **`git` and `gh`: `metab`.** `metab` runs them; the app only finds them and passes
  their directories on `PATH`. So their minimums live in `metab`, beside the code that
  needs them, with the reason: `git`’s already do, and `gh`’s goes in
  jlevy/metabrowser#581’s `gh_status.py` (Phase 2). The app reads them from
  `metab --doctor --json` and never copies them.

Why `metab` and not the app for `gh`: the code that calls `gh auth status --json` or
`gh stack` knows which release it needs; a copy in Swift would drift from it; a `metab`
upgrade that needs a newer `gh` would otherwise need an app release; and the CLI, the
skill, and the page all need the same answer without the app.
`--doctor --json` is already the one report the app reads.
AGENTS.md states the rule.

### The Versioning Contract

The owner’s rule, as written into
[Publishing](../../../publishing.md#choosing-a-version), AGENTS.md, and
`MetabRequirement`’s doc comment:

- A `metab` change the app depends on is released as a new minor or major version, never
  as a patch. A patch only fixes bugs, and keeps what the app reads.
- So `MetabRequirement.minimumRelease` is always `X.Y.0`, and a patch never raises it.
- **What the app reads** is its contract: the serve flags in `CLIServeLaunch` (`--host`,
  `--port`, `--no-open`, `--exit-on-eof`); `--present … --dry-run --format json`
  (`PresentDryRun`); `--recent --json`, `--recent-add`, `--recent-forget`, and
  `--recent-clear` (`RecentTargets`); `--api /api/cache/sources --format json`
  (`RepositoryCache`); `GET /api/identity`; `--version`’s line; `--doctor`; a failed
  start’s `Error:` line and the clone report (`GitHubFailure`, `StartProgress`); the
  exit statuses in `cli/exit_codes.py`; and the `Info.plist` key `--present` reads.
  The app contract golden (separate PR) pins this list; this plan does not.

Checks, both in Phase 1:

- `tests/test_macos_app_pins.py` fails when `minimumRelease` names a patch, and when
  `pyproject.toml` stops bumping the minor position for a development build.
  It runs in every CI Python job, where the macOS workflow’s path filter would not run
  the app’s own tests.
  `MetabVersionTests.theMinimumIsAMinorRelease` holds the same in Swift.
- The bump matters: with the default patch bump, a checkout past `v0.12.0` reported
  `0.12.1.devN`, below a `0.13.0` minimum, and the app would refuse every development
  build. With `bump = { enable = true, index = 1 }` it reports `0.13.0.devN`.

A check that flags a change to a contract surface without a raised minimum is not in
this plan: the app contract golden (separate PR) covers the surface.

### One Requirement Declaration per Tool

Phase 3 generalizes `MetabRequirement` into a `ToolRequirement` value in ShellCore with,
for each tool:

- **name**, and **minimum** with **the reason it was last raised**: for `metab`, from
  the app’s own constant; for `git` and `gh`, from the doctor’s report.
- **how it is found**: for `metab`, the discovery order above; for `git` and `gh`,
  `resolveTools`.
- **how its version is read**: `metab --version` (with the flag probe), `git --version`,
  `gh --version`, by the app for `metab` and by `metab` for the rest.
- **upgrade instructions by install method**, chosen from the canonical path of the
  executable found:

| Tool | Install method | Detected from | Upgrade command |
| --- | --- | --- | --- |
| `metab` | uv tool | under `uv tool dir` | `uv tool install --upgrade 'metabrowser>=X.Y.0'` |
| `metab` | pipx | under pipx’s `venvs` | `pipx install --force 'metabrowser>=X.Y.0'` |
| `metab` | checkout | `.venv/bin/metab` beside a `pyproject.toml` | `git pull && make install` in the checkout |
| `gh` | Homebrew | under a Homebrew `Cellar` | `brew upgrade gh` |
| `gh` | MacPorts | under `/opt/local` | `sudo port upgrade gh` |
| `gh` | official installer | anything else | the install page, `https://cli.github.com/` |
| `git` | Homebrew | under a Homebrew `Cellar` | `brew upgrade git` |
| `git` | Command Line Tools | `/usr/bin/git` or `/Library/Developer/CommandLineTools` | `brew install git`, since Apple’s Git trails the floor |

The commands for `git` and `gh` belong to `metab`, beside their minimums, and arrive in
the doctor’s `remedy`, so the app shows them and the CLI prints the same; the app keeps
only `metab`’s own, since it must work when no `metab` runs.

### The Doctor Report

Phase 2 makes `metab --doctor` the one report on everything a setup needs, keeping
today’s keys and adding a `checks` list.
Each check has an `id`, a `title`, a `state` (`ok`, `warning`, `problem`, or `skipped`),
a one-line `summary`, `details`, and a `remedy` (`text`, and a `command` or `url` when
one fixes it). The text output prints one line per check and the remedy under it.

| `id` | What it checks | Bound |
| --- | --- | --- |
| `metab` | Version, executable, install method, and whether the editable install is stale | none |
| `python` | Interpreter path and version against `requires-python` | none |
| `git` | Path and version against the acquisition and partial-clone floors | `git --version` timeout |
| `github` | jlevy/metabrowser#581’s check, plus the declared `gh` minimum | jlevy/metabrowser#581’s deadlines |
| `config` | Configuration directory resolves, is private, and `config.yml` parses | file size cap |
| `cache` | Cache directory resolves, is private and writable, and its free space | one `statvfs` |
| `plugins` | Today’s plugin and contract checks | none |
| `markdown_renderer` | The Markdown child starts and answers one render | the inert render deadline |
| `browser` | A browser is registered for `webbrowser` | none |
| `macos_app` | On macOS: an app at `APP_INSTALL_LOCATIONS`, its version, and its build’s minimum `metab` against this one | `Info.plist` size cap |
| `network` | github.com resolves and accepts a TLS connection | a few seconds |
| `recent_targets` | The store reads, in a format this release knows | file size cap |
| `locks` | No hierarchy lock is held by a process that is gone; a live refresh is named | none |

- **Exit status.** As today, only a `problem` in a check `metab` cannot serve a local
  folder without (`python`, `config`, `cache`, `plugins`, `markdown_renderer`) exits 1.
  GitHub, `git`, the network, and the app report at most a `warning`, as
  jlevy/metabrowser#581’s section never changes the status, so the release gate’s
  isolated run stays offline-safe.
- **The app’s minimum, readable by `metab`.** The app’s `Info.plist` gains a key naming
  its minimum `metab`, set from `MetabRequirement` at build time and held to it by
  `tests/test_macos_app_pins.py`, so the `macos_app` check can say “this app needs
  `metab` X.Y.0; this is A.B.C”.
- **Parity.** Each check is a functional aspect in the
  [Parity Registry](../../architecture/arch-parity-registry.md) with a golden,
  `tests/golden/cli-doctor.tryscript.md`, covering text and JSON in a sandboxed home
  with stand-in `git`, `gh`, and app bundles, as jlevy/metabrowser#581’s
  `tests/fixtures/github-status/gh` does.
  A route is not needed: the app runs the CLI, and jlevy/metabrowser#581’s route already
  serves the GitHub part to the page.

### Check Setup… in the App

- **Where.** Help > Check Setup…, beside Reveal Logs Folder, and the Run Doctor button
  in Settings opens the same window.
- **What it runs.** `metab --doctor --json` from the selected runtime, in a server’s
  environment with the tool directories (`ChildEnvironment`), bounded by
  `RuntimeDiscovery.doctorTimeout`.
- **What it shows.** One row per check, with its state’s symbol, summary, and remedy; a
  command has Copy, as jlevy/metabrowser#571’s `GitHubFailureDetails` steps do.
  Copy Report copies the text form; Check Again runs it again.
- **Rows only the app knows,** first: the app’s version and minimum `metab`, the `metab`
  it runs and how it was found, and the `git` and `gh` it found, so a mismatch with
  Terminal’s shows.
- **No `metab`.** The window shows the `metab` requirement and `SetupGuide`’s steps
  instead of a report.
- **An older `metab` without `checks`** cannot occur: the app needs the minimum that
  adds them (no compatibility layer; the minimum is raised in the same change).

## Implementation Plan

### Phase 1: The Contract (in this plan’s pull request)

- [x] `MetabRequirement.minimumRelease` becomes `0.13.0`, with the contract in its doc
  comment. The next `metab` release is therefore `0.13.0`, not `0.12.1`.
- [x] `pyproject.toml` bumps the minor position for a development build.
- [x] `tests/test_macos_app_pins.py` and `MetabVersionTests` hold the minimum to `X.Y.0`
  and the bump to the minor position.
- [x] [Choosing a Version](../../../publishing.md#choosing-a-version) in Publishing,
  AGENTS.md, [Development](../../../development.md), and
  [the version floor](../../architecture/arch-macos-app.md#the-version-floor).
- [x] The guides and the skill that state the minimum, held by
  `tests/test_user_guide_values.py`.

### Phase 2: A Complete Doctor (after jlevy/metabrowser#581 merges)

- [ ] `gh`’s minimum in `gh_status.py`, with the reason, and `gh_too_old` decided by it
  as well as by a rejected subcommand.
- [ ] The `checks` list and each check in the table above, in a new `cli/doctor.py` that
  `doctor_plugins` calls; text and JSON; bounded.
- [ ] The app’s `Info.plist` key for its minimum `metab`, and its pin.
- [ ] The golden, the parity rows, and the installed-wheel smoke run.
- [ ] `docs/command-line.md` and [installation](../../../installation.md) name the
  doctor as the first step when something fails.

### Phase 3: Requirements and Check Setup… in the App

- [ ] `ToolRequirement` in ShellCore, `MetabRequirement` becoming its `metab` entry,
  with the install-method detection and commands above, and tests for each method.
- [ ] A `DoctorReport` decoded from `--doctor --json`, and the Check Setup… window, menu
  item, Copy Report, and Check Again; Settings’ Run Doctor opens it.
- [ ] `MetabRequirement.minimumRelease` raised to the release that adds `checks`, which
  is a minor one by Phase 1’s rule.
- [ ] `docs/macos-app.md` says where Check Setup… is and what it shows.

### Follow-Up

- The app contract golden (separate PR): one golden over every flag, route, JSON field,
  output line, and exit status the app reads.

## Open Questions

1. **The 0.x period.** Proposed: before 1.0 the minor release is the boundary for both
   directions, so a `0.Y.0` may add what the app needs and may also change what an older
   app read, and says so in its notes; the app declares a minimum and no maximum.
   The alternative is a ceiling, the app refusing a `metab` of a later minor than it was
   built for, which would make every `metab` minor release need an app release.
2. **A bug fix the app needs.** Proposed: it ships as a minor release, so the minimum
   never names a patch.
   The alternative is to allow a patch minimum for fixes only, which the check would
   then have to tell apart.
3. **The next release is 0.13.0, not 0.12.1.** Phase 1 raises the app’s minimum to
   `0.13.0`, so the release that carries `--present`, `--recent`, and the identity route
   is `0.13.0`.
4. **A released app with a newer `metab`.** AGENTS.md keeps no compatibility with an
   older app. Once the app is published, a user can update `metab` without updating the
   app. Should a `metab` minor release keep what the last published app reads until an
   app release that no longer needs it has shipped?
5. **The network check.** Proposed: `--doctor` opens one TLS connection to github.com,
   which `gh auth status` already does when `gh` is signed in, and a `--doctor` run with
   `METABROWSER_OFFLINE=1` or no network reports `skipped`, not `problem`.
6. **Where Check Setup… lives.** Proposed: Help > Check Setup…. The alternative is
   Metabrowser > Check Setup…, beside Settings….

## References

- [Native macOS app](plan-2026-11-10-native-macos-app.md) and
  [publishing the macOS app](plan-2026-11-16-macos-app-publishing.md)
- [Opening anything from the CLI and the app](plan-2026-11-17-open-anything-from-cli-and-app.md),
  whose Sign-In section jlevy/metabrowser#581 implements
- [macOS app architecture](../../architecture/arch-macos-app.md)
- [Publishing](../../../publishing.md) and [Installation](../../../installation.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
