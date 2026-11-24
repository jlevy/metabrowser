# Plan for the App’s Command-Line Dependencies and a Complete Doctor

**Date:** 2026-11-18

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Phase 1 (the versioning contract) shipped in jlevy/metabrowser#590. Phases 2
and 3 are in the pull request that checks them off below, on top of the GitHub status
check (`mb-si2g`, jlevy/metabrowser#581). The checks Phase 2 did not build, and why, are
under [What Phase 2 Built](#what-phase-2-built).
Bead `mb-bxli` tracks the work.
[Owner Decisions](#owner-decisions) lists what the owner decides.

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
  needs them, with the reason.
  `git`’s already do. `gh`’s is new in Phase 2: one constant in `gh_status.py`, with its
  reason, which is the only `gh` minimum anywhere.
- **The app reads them, never a second way.** The app gets `gh`’s path, version,
  minimum, state, and remedy from the doctor’s `github` object, and `git`’s from its
  `git` check. It runs neither tool and parses neither version itself, and ShellCore
  declares no `gh` or `git` version.

Why `metab` and not the app for `gh`: the code that calls `gh auth status --json` or
`gh stack` knows which release it needs; a copy in Swift would drift from it; a `metab`
upgrade that needs a newer `gh` would otherwise need an app release; and the CLI, the
skill, and the page all need the same answer without the app.
`--doctor --json` is already the one report the app reads.

Review A6 on jlevy/metabrowser#581 sets how `gh_status` uses the minimum:

- `gh_too_old` compares `gh_version` with the minimum.
  `_VERSION_LINE` stays the one `gh` version parser, and the probe that finds an unknown
  flag stays as a fallback.
- `gh_too_old`’s fix is the upgrade for the install method found.
- The doctor’s `github` object gains the minimum; no second `gh` entry is added.

Phase 2 was to add a check that ShellCore holds no version literal for `gh` or `git`. It
is not built: a text search cannot tell a requirement from a comment that records a
measured version, and the structure already holds the rule, since ShellCore has no `gh`
or `git` requirement type and `DoctorReport` is the only place the app reads either
version. AGENTS.md gains no rule without the check.

### The Versioning Contract

The rule, its reason, and how to raise the minimum are written once, in
[Choosing a Version](../../../publishing.md#choosing-a-version); AGENTS.md,
`MetabRequirement`’s doc comment, and the architecture document link to it.
In short, a `metab` change the app depends on is a new minor or major release, a bug fix
that keeps what the app reads may be a patch, and so `MetabRequirement.minimumRelease`
is always `X.Y.0`. How 0.x, 1.0 and later, and a fix the app needs are treated are
[Owner Decisions](#owner-decisions).

Examples of what the app reads, for the app contract (follow-up) to settle: the serve
flags in `CLIServeLaunch`, `--present … --dry-run --format json`, the `--recent` modes,
`--api /api/cache/sources --format json`, `GET /api/identity`, `--version`’s line,
`--doctor`, a failed start’s `Error:` line and the clone report, the exit statuses in
`cli/exit_codes.py`, and the `Info.plist` key `--present` reads.
This plan keeps no list of its own.

Phase 1’s checks, all in `tests/test_macos_app_pins.py`, which runs in every CI Python
job, where the macOS workflow’s path filter would not run the app’s own tests:

- the minimum names no patch;
- it is at most the next minor release after the latest release, the first `## X.Y.Z`
  heading in `CHANGELOG.md`, and `isReleased` is false while it is newer than that
  release;
- `pyproject.toml` bumps the minor position for a development build, so a checkout past
  `v0.12.0` reports `0.13.0.devN`, not `0.12.1.devN`, which is below `0.13.0`;
- `[tool.uv]` `cache-keys` include the commit and the tags, so `make install` rebuilds a
  checkout’s version after each commit or tag.
  By default uv rebuilds it only when `pyproject.toml` changes, so after the next raise
  of the minimum every checkout would keep its old version and the app would refuse it.

`MetabVersionTests.theMinimumIsAMinorRelease` checks only the first of these in Swift.
A check that flags a change to a contract surface without a raised minimum is not in
this plan: the app contract golden (separate PR) covers the surface.

### One Requirement Declaration per Tool

Each tool’s requirement is declared once, by the program that runs it, with the same
fields:

- **name**, and **minimum** with **the reason it was last raised**;
- **how it is found**;
- **how its version is read**;
- **upgrade instructions by install method**, chosen from the canonical path of the
  executable found.

| Tool | Declared in | Found by | Version read by |
| --- | --- | --- | --- |
| `metab` | `MetabRequirement` in ShellCore | the app’s discovery order above | the app: the flag probe and `--version` |
| `gh` | `gh_status.py` (Phase 2) | `gh_executable`, on the `PATH` the app gives a server | `gh_version` and `_VERSION_LINE` |
| `git` | `git/process.py` and `checkout_revisions.py` | `git` on that `PATH` | `parse_git_version` |

Only `metab`’s requirement is in Swift, since only `metab` is checked by the app.
Phase 3 adds the install-method commands to it; Phase 2 adds them to `gh`’s and `git`’s
in `metab`, and the doctor reports them as each check’s remedy.
A Swift `gh` or `git` entry would be a second read path, which review A6 on
jlevy/metabrowser#581 rules out, unless the app itself starts to run the tool, which
would then be the reason for it.

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
GitHub stays where jlevy/metabrowser#581 puts it, the top-level `github` object, which
gains the `gh` minimum and its reason, and whose `fix` for `gh_too_old` becomes the
upgrade for the install method found.
`checks` has no `github` entry, so `gh` is reported once.
Each check has an `id`, a `title`, a `state` (`ok`, `warning`, `problem`, or `skipped`),
a one-line `summary`, `details`, and a `remedy` (`text`, and a `command` or `url` when
one fixes it). The text output prints one line per check and the remedy under it.

| `id` | What it checks | Bound |
| --- | --- | --- |
| `metab` | Version, executable, install method, and whether the editable install is stale | none |
| `python` | Interpreter path and version against `requires-python` | none |
| `git` | Path and version against the acquisition and partial-clone floors | `git --version` timeout |
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
- **What it shows.** One row per check and one for the `github` object, with its state’s
  symbol, summary, and remedy; a command has Copy, as jlevy/metabrowser#571’s
  `GitHubFailureDetails` steps do.
  Copy Report copies the text form; Check Again runs it again.
- **`gh` and `git` come from the report.** The `github` row reads `gh_path`,
  `gh_version`, and the minimum from the doctor, and the `git` row its `git` check.
  The doctor runs with the directories the app found first on `PATH`, so these are the
  tools the app’s servers use, and the app never runs `gh --version` or parses it.
- **Rows only the app knows,** first: the app’s version and minimum `metab`, and the
  `metab` it runs and how it was found, so a mismatch with Terminal’s shows.
- **No `metab`.** The window shows the `metab` requirement and `SetupGuide`’s steps
  instead of a report.
- **An older `metab` without `checks`** can run: a checkout’s development build of
  `0.13.0` from before the checks meets the floor.
  The window shows the rows the report has, says the checks are missing, and offers the
  upgrade for how that `metab` was installed.
  The floor is not raised, since `0.13.0` is unreleased and its release has the checks.

### What Phase 2 Built

`cli/doctor.py` has the checks `plugins`, `open_in`, `metab`, `git`, `config`, and
`cache`, in that order, and the app shows one row for each and one for the `github`
object, whose step is a `remedy` of the checks’ shape, so it reads no row or step from a
sentence (review A2 on jlevy/metabrowser#596). `python` is a detail of the `metab`
check, and `macos_app` is that check’s comparison with the app that runs Check Setup…,
or else the app `--present` would open, whose `Info.plist` declares its minimum.
`plugins` is also still the doctor’s verdict and `problems`. No check reports `skipped`,
so the states are `ok`, `warning`, and `problem`.

Of the other ways a setup breaks that [Background](#background) lists:

- **Configuration overrides** are built: a directory that `METABROWSER_CONFIG_DIR`,
  `METABROWSER_CACHE_DIR`, or an `XDG_` variable names in a terminal is a warning when
  an app was found, naming the directory the app’s servers use, since the app passes
  none of them (`ChildEnvironment`). The reverse cannot happen: the app sets none.

- **A full disk** is built: free space on the cache’s volume below the reserve a first
  clone leaves free (`cache/free_space.py`), so that every first clone that does not
  borrow from a checkout is refused, is a warning, and a missing directory that cannot
  be created is a problem.

- **Two `metab`s** is deferred: the doctor knows only the `metab` that runs it, and
  Check Setup… runs the app’s, whose path heads Copy Report; comparing it with
  Terminal’s needs the login shell’s `PATH`, which the app reads only at discovery.

- **Folder privacy prompts** are deferred: the doctor runs as the app’s child but holds
  no folder, and macOS reports a denial only when a folder is read, so no read here
  could tell a denial from a folder the user has not opened.

- **Not uv.** `metab` never runs uv, so a missing or old uv breaks nothing the doctor
  can see; uv appears only in the step that upgrades a uv install.

- **Not the network.** Off by default, as [Owner Decisions](#owner-decisions) item 6
  proposes; `gh auth status` already reaches github.com when `gh` is signed in.

- **Not built, as follow-ups:** `markdown_renderer` (starting the child adds seconds to
  every doctor run), `browser`, `recent_targets`, `locks`, and the stale editable
  install. Each needs its own bound and fixture, and none blocks serving a folder.

## Implementation Plan

### Phase 1: The Contract (in this plan’s pull request)

- [x] `MetabRequirement.minimumRelease` becomes `0.13.0`. The next `metab` release is
  therefore `0.13.0`, not `0.12.1`.
- [x] `pyproject.toml` bumps the minor position for a development build, and its
  `[tool.uv]` `cache-keys` rebuild a checkout’s version after each commit or tag.
- [x] `tests/test_macos_app_pins.py` checks the four things above, and
  `MetabVersionTests` the first.
- [x] [Choosing a Version](../../../publishing.md#choosing-a-version) in Publishing,
  linked from AGENTS.md, [Development](../../../development.md),
  [the version floor](../../architecture/arch-macos-app.md#the-version-floor), and
  `MetabRequirement`’s doc comment.
- [x] The guides and the skill that state the minimum, held by
  `tests/test_user_guide_values.py`.

### Phase 2: A Complete Doctor (after jlevy/metabrowser#581 merges)

- [x] `gh`’s minimum, one constant in `gh_status.py` with its reason; `gh_too_old`
  decided by comparing `gh_version` with it, with the unknown-flag probe as a fallback;
  its fix the install-method upgrade; and the `github` object extended with it (review
  A6 on jlevy/metabrowser#581).
- [x] The `checks` list in a new `cli/doctor.py` that `doctor_plugins` calls; text and
  JSON; bounded. [What Phase 2 Built](#what-phase-2-built) lists the checks.
- [x] ~~A check that ShellCore holds no version literal for `gh` or `git`~~, not built:
  [A Minimum Lives with the Program That Runs the Tool](#a-minimum-lives-with-the-program-that-runs-the-tool)
  says why.
- [x] The app’s `Info.plist` key for its minimum `metab`, and its pin.
- [x] The golden, the parity row, and the installed-wheel smoke run, which now gives the
  doctor a private cache directory of its own.
- [x] `docs/command-line.md` and [installation](../../../installation.md) name the
  doctor as the first step when something fails.

### Phase 3: Requirements and Check Setup… in the App

- [x] `MetabRequirement` gains `metab`’s install-method detection and commands above
  (`MetabInstall`), with tests for each method; `tests/test_macos_app_pins.py` holds
  them to the doctor’s. ShellCore gets no `gh` or `git` requirement.
- [x] A `DoctorReport` decoded from `--doctor --json`, and the Check Setup… window, menu
  item, Copy Report, and Check Again; Settings’ Check Setup… opens it.
- [x] `MetabRequirement.minimumRelease` is already `0.13.0`, the unreleased minor
  release that adds `checks`.
- [x] `docs/macos-app.md` says where Check Setup… is and what it shows, and the
  [hand checks](../../qa/qa-macos-app-hand-checks.md) cover the window.

### Follow-Up

- The app contract golden (separate PR): one golden over every flag, route, JSON field,
  output line, and exit status the app reads.
  `--doctor --json` is pinned by `tests/golden/cli-doctor.tryscript.md`, whose
  `metab --doctor --json` test it can cite.
- The checks [What Phase 2 Built](#what-phase-2-built) lists as not built.

## Owner Decisions

Each is a proposal until the owner decides it.

1. **The 0.x period.** Proposed: before 1.0 the minor release is the boundary in both
   directions, so a `0.Y.0` may add what the app needs and may also change what an older
   app read, and says so in its notes; the app declares a minimum and no maximum.
   The alternative is a ceiling, the app refusing a `metab` of a later minor than it was
   built for, which would make every `metab` minor release need an app release.
2. **1.0 and later.** Proposed: a change that removes or alters what a released app
   reads is a major release, and one that only adds what a newer app needs is a minor
   release, as semantic versioning has it.
3. **A bug fix the app cannot work without.** The owner’s words allow a bug fix as a
   patch, and a fix that keeps what the app reads stays one.
   Proposed: a fix the app needs, which would raise the minimum, ships as a minor
   release, so the minimum never names a patch, as Phase 1’s check holds.
   The alternative is a patch minimum for such fixes, which the check would then have to
   allow.
4. **The next release is 0.13.0, not 0.12.1.** Phase 1 raises the app’s minimum to
   `0.13.0`, so the release that carries `--present`, `--recent`, and the identity route
   is `0.13.0`.
5. **A released app with a newer `metab`.** AGENTS.md keeps no compatibility with an
   older app. Once the app is published, a user can update `metab` without updating the
   app. Should a `metab` minor release keep what the last published app reads until an
   app release that no longer needs it has shipped?
6. **The network check.** Not built: no setup check opens a connection, and only
   `gh auth status`, in the GitHub section, reaches github.com.
   Proposed: a `network` check that opens one TLS connection to github.com, at most a
   `warning`, so that a failure without `gh` is named too.
   The release gate’s isolated doctor run would then need it switched off.
7. **Where Check Setup… lives.** Built as Help > Check Setup…, with a button of the same
   name in Settings. The alternative is Metabrowser > Check Setup…, beside Settings….
8. **uv.** Proposed: the doctor does not check uv, which `metab` never runs; it names uv
   only in the step that upgrades a uv install.

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
