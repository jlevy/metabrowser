# Plan for Opening Anything from the CLI, the Skill, and the macOS App

**Date:** 2026-11-17

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Phase 1 partly built, Phase 2 not started; [Progress](#progress) says what
landed where. Epic `mb-jl8o` tracks every item below as a bead.
It assesses what exists and sets the path for one invocation that opens any folder,
file, or GitHub URL in the native app or a browser, whichever applies.
It takes a first-release slice out of Phase 3 of the
[native macOS app plan](plan-2026-11-10-native-macos-app.md) and leaves the rest of that
phase where it is. [Open Questions](#open-questions) lists the owner’s decisions.

## Progress

As of 2026-11-18. Background and Design below record the code and the intent as of
2026-11-17; where what shipped differs, this section and the architecture documents it
links describe what was built.

### Landed

- **`metab TARGET --present`** (jlevy/metabrowser#540): resolution with no clone and no
  server import, `--dry-run`, the report, detection through LaunchServices, delivery by
  `open -b`, and distinct exit codes for a refusal, no app, and a blocked LaunchServices
  (`cli/exit_codes.py`). A commit URL now opens at `/commit/<id>`. It differs from the
  design in four ways:
  - JSON is `--format json`; `--json` is refused with `--present`.
  - Delivery is to the app or nowhere (`delivered_to` is `app` or `none`), and the
    report never claims a window showed the target.
  - Detection tries the release bundle identifier and then the dev one, unless
    `--app-bundle-id` or `METABROWSER_APP_BUNDLE_ID` names one.
  - It sends only to a build installed in an Applications folder whose `Info.plist`
    declares `MetabrowserOpensURLs` (`cli/present.py`).
- **GitHub links in the app** (jlevy/metabrowser#539): `AppDelegate` accepts `https`
  GitHub links, resolves each with `--present --dry-run --format json`, and shows
  `metab`’s refusal. `SessionRoot` is the plan’s `RootIdentity`: it keys a session by a
  folder’s path or a repository’s canonical URL, never by the pin.
  A link into a repository that has a window switches that window to the link’s
  revision, and a repository the cache does not hold asks before it clones.
  Repository tabs stay out of the saved session.
  The app’s setup refuses a `metab` without `--present`
  (`MetabRequirement.requiredFlags`).
  [GitHub Links](../../architecture/arch-macos-app.md#github-links) describes it.
- **File > Open URL…** (jlevy/metabrowser#560), on Command-L, is the plan’s Open
  Location…. It takes a full GitHub URL, with no local path and no `owner/repo`
  shorthand. The app checks the URL with the gate it applies to a sent link, then asks
  `--present --dry-run --format json`, and opens it in its mirror, always.
  File > Open… became Open Folder….
- **Recent targets** (jlevy/metabrowser#546), in place of a recents section drawn from
  the saved session: `metab` keeps one list of recent folders and mirrors in its
  configuration directory, recorded at serve start, and the app’s Open Recent and Dock
  menu draw it, mirrors included
  ([Recent Targets](../../architecture/arch-recent-targets.md)).
- **GitHub’s anchor for one file of a pull request** (jlevy/metabrowser#574):
  `/pull/<n>/files#diff-<hash>` opens at `/pull/<n>/files/<path>`, named offline from
  the cached list of changed files or the record’s comparison, and at the Changes tab,
  with the reason, when neither names it.
  A line in the anchor is reported, not yet scrolled to, and `--present --dry-run`
  reports no page for such a URL, since only the cache can name the file.
- **The skill and its docs** (jlevy/metabrowser#562): “Hand the User a Page” uses
  `--present`, falls back to the `--no-open` server, and documents the Claude Code and
  Codex sandbox settings.
- **Open Modes** (jlevy/metabrowser#558):
  [Open Modes](../../architecture/arch-open-modes.md) defines plain folder, repository
  folder, and mirror, records the owner’s decisions that answer Questions 1 and 2 below,
  and tracks the shared work in its Implementation Status table.
  jlevy/metabrowser#559 then gave a checkout’s window the branch and tag chooser and
  `metab PATH --ref NAME`, so a repository folder shows any ref read-only beside its
  working tree.

### Remaining

- Browser delivery with a detached server (`mb-kze0`), and the `open_in` preference that
  chooses between the app and a browser (`mb-gh6l`).
- The GitHub status check, its `--doctor` section and route, the check before a first
  clone or pull request read, and token scopes (`mb-si2g`).
- Clone progress and GitHub failure states in the app’s status view (`mb-m0ry`).
- Saved tabs for repository windows (`mb-682q`).
- Outside this epic, on the same path: the walk-up resolver that `--present` and the app
  will resolve through (`mb-2wfk`), Open URL…’s offer of a known checkout (`mb-bkk2`),
  and a mirror entry’s target in the recent list, so that Open Recent can reopen a pull
  request (`mb-8bds`).

## Overview

The owner asked, on 2026-11-17, that as the macOS app nears its first release, the skill
and the way `metab` is invoked work with both a command-line `metab` and the native app:
use the app when it is installed and preferred, and otherwise the CLI and a browser.
More broadly:

> “anything that’s possible in the Metabrowser UI, both web and desktop, is easily
> controllable from the CLI. We need binding points and names for all the different
> actions and occurrences in the UI … incremental goals of being able to open any PR or
> any file, at a minimum.”

And GitHub URLs of any sort should open the same way from the CLI, from the app’s File
menu, and from an agent: in the right window for the repository, cloning or reusing the
cache, with `gh` checked and any sign-in problem surfaced so the user can fix it.

This plan does that in two phases.
Phase 1 is a release-scoped slice: one command, `metab TARGET --present`, that resolves
any target `metab` accepts, chooses the app or a browser from a stored preference and
the app’s presence, hands the target over, and reports what it did; the app gains GitHub
URLs and File > Open Location…. Phase 2 is the round trip: a reply from the app,
navigation of a page that is already open, and named UI commands that the CLI can list
and invoke.

## Goals

- **One invocation for agents and people.** `metab TARGET --present` opens a folder, a
  file, or any GitHub URL `metab` accepts, in the app when it is installed and
  preferred, otherwise in a browser, and prints and exits with what it did.
  The skill uses it, under `metab` or `uvx`, with no platform branching of its own.
- **A stored preference** for where things open, defaulting to the app whenever it is
  detected, which can be turned off, or made strict so that a missing app fails.
- **GitHub URLs anywhere.** A repository, pull request, file, folder, or commit URL
  opens in the app from `open`, from File > Open Location…, and from `--present`, as
  `metab URL` already does in a browser: in a window for that repository, cloning into
  the cache or reusing it.
- **Sign-in that explains itself.** Before work that needs GitHub, `gh` is found and its
  sign-in checked, and every failure names the step that fixes it, the same way in the
  CLI, the page, and the app.
- **Names for what the UI does.** Every command the UI can run has a stable id that the
  CLI can list (Phase 2) and invoke (Phase 2), starting from the ids the shortcut
  registry already has.
- **Parity.** Every decision above is a `metab` mode or route with a golden; the app
  adds only platform behavior.

## Non-Goals

- GitHub Enterprise and other forges: `GH_HOSTNAME` is fixed to github.com, as the
  [pull request mirror plan](plan-2026-11-02-pr-review-mirror-and-checkout.md) records.
- Registering the app as the handler for `https://github.com` links.
  Browsers own `https`; the app receives a GitHub URL only when it is sent there.
- Running `gh auth login`, an installer, or any credential flow from the app.
  The app shows the command and waits, as it does for `metab` setup today.
- Choosing the security model for roots that agents add, which the native app plan
  defers to its Phase 4.
- Windows and Linux desktop apps.

## Background

The facts below were gathered from the code on 2026-11-17; references are to the files
that own them.

### What `metab` Accepts

- **GitHub URLs as ROOT.** `classify_root_argument` (`src/metabrowser/cache/urls.py`)
  runs `GithubUrlReducer` (`builtin_plugins/github/urls.py`, whose module docstring is
  the table of shapes): a repository, `/tree/…`, `/blob/…` with line anchors and
  `?plain=1`, `raw.githubusercontent.com`, `/commit/<sha>`, `/pull/N` with `/files`,
  `/checks`, and `/commits/<oid>`, and SSH spellings rewritten to `https`. Repository
  pages such as `/issues`, `/pulls`, and `/compare`, account pages, `http:`, and URLs
  carrying credentials are refused as `unsupported_github_url`.
- **Opening one.** `run_serve_pin` (`cli/git_pin_cli.py`) acquires or reuses a bare
  mirror in the cache, pins the selection (a pull request pins `refs/pull/<n>/head`
  after `open_pull_for_cli`), and opens at `selection_view_href` (`cli/selection.py`):
  `/pull/<n>[/files|/checks]`, `/view/<path>[#L…]`, or `/view/`. A pull request that
  cannot be read falls back to the default branch, says why on the `pull_request` line,
  and still exits 0.
- **Gaps:** the gh shorthand `owner/repo` is a local path; GitHub’s anchor for one file
  in a pull request (`/pull/N/files#diff-<hash>`) is ignored although the server has
  `/pull/<n>/files/<path>`; a commit opens at `/view/` rather than `/commit/<sha>`.

### How `gh` Is Checked

- `GhFailureState` (`builtin_plugins/github/gh.py`) names `gh_missing`, `gh_too_old`,
  `not_logged_in`, `rate_limited`, `not_found_or_private`, `network_error`, and
  `gh_failed`; `PullDataState` (`gh_lists.py`) extends it.
  The page explains each and links to the GitHub CLI for install and upgrade.
- Git clones use only `gh auth git-credential`, scoped to github.com
  (`credential_helper_args`, `provider.py`); without `gh` a private clone fails as
  `not_found_or_private` with a hint to sign in.
- **Gaps:** nothing checks sign-in before a clone or a pull request read starts, so a
  failure arrives mid-flow; token scopes are never read; `--doctor` does not report the
  GitHub account; the app never sees these states except in a server log or the page.

### What the App Accepts

- Every open (Open…, Open Recent, Dock, Open With, `open -a`, drops) reaches
  `AppDelegate.request`, which returns at once for any URL that is not a file URL, with
  no message. `Info.plist` declares no URL scheme, and `apps/macos/scripts/common.sh`
  already renames a scheme for the dev variant.
- A folder session is keyed by its canonical path, and so are its log name, its
  pre-ready title, `OpenTarget`, `RootAdmission`, `SavedTab.root`, Open Recent, and the
  folders waiting for a runtime.
- What already fits a URL root: `CLIServeLaunch` passes ROOT through unchanged,
  `parseServingLine` accepts the normalized URL `metab` prints, and `FolderIdentity` has
  a `mirror` kind whose title is the repository and pin, read from `/api/identity` once
  the server is ready.
- The File menu (`MainMenu.swift`) has no Open Location….
- The app passes `gh` on `PATH` but drops `GH_TOKEN` and `GITHUB_TOKEN`
  (`ChildEnvironment`), and never runs `gh auth status`.
- Release and dev builds have the bundle identifiers that `scripts/common.sh` sets, and
  both are named `Metabrowser.app`. No CLI helper ships in the bundle.

### What Can Name a UI Action

- **Addresses** name most of what a user can select: `/view/`, `/commit/`, `/pull/…`,
  `/pulls`, and fragments ([the map](../../architecture/arch-views-models-routes.md)).
  The view tab and the main tab are not in the URL; `_mb_view` is planned there.
- **Commands** exist only in each page’s JavaScript: the shortcut registry
  (`static/keyboard-shortcuts.js`) holds descriptors with ids such as `shell.home`,
  `main-tabs.pulls`, `tree.next`, `pulls.open`, and `diff.layout`, and `invoke(id)` runs
  one if its scope and target are live.
  No route lists them, and the
  [menu primitives plan](plan-2026-08-06-menu-primitives-and-file-actions.md)’s action
  registry is not built.
- **Push to a page:** `/api/events` carries file-system and capability events to
  anonymous connections; there is no `navigate` event and no client identity.
- **Parity machinery** ([registry](../../architecture/arch-parity-registry.md)) already
  checks routes and runs browserless sessions against production JavaScript, so a
  command catalog can be pinned the way `tests/test_keymap.py` pins the key table.

### What Is Already Planned

Phase 3 of the native app plan has host mode (`mb-qzny`), the live-server registry
(`mb-5xi4`), control verbs on an owner-only socket (`mb-1zyp`), pages that follow
`navigate` (`mb-54r1`), the front door (`mb-idri`), the `metabrowser://` scheme with a
rendezvous reply and in-app confirmation (`mb-rtgh`), and the skill (`mb-ko5d`). The
front door depends on all of the server-side work, so nothing reaches the app from an
agent until host mode ships.
The [topology brief](../../research/research-2026-11-10-native-app-server-topology.md)
(“Show X” End to End, Control Plane) has the reasoning, including why an agent must
reach the app through LaunchServices and never by executing its binary.

## Design

### Approach

Hand a target to the app with what LaunchServices already delivers,
`open -b <bundle> TARGET`, and let the app pass it to `metab`, which already resolves
folders, files, and GitHub URLs.
That needs no server-side control plane, so it can ship with the first release, and
`--present` keeps its interface when Phase 2 replaces the transport with a rendezvous
that replies.

Alternatives considered:

- **Branching in the skill** (check the platform and the app, call `open -a`): logic in
  prose, untested, different under each agent, blind to the preference, and unable to
  report. Rejected.
- **A shim or a helper inside the bundle:** a second entry point that exists only with
  the app, so the skill still branches, and executing the app’s binary bypasses
  LaunchServices and makes the caller the responsible process for privacy prompts.
  Rejected.
- **Waiting for Phase 3 entire:** correct, but nothing reaches the app until host mode,
  the registry, and the socket ship.
  Rejected for the first release; kept as Phase 2.

### Resolution and Delivery

`--present` is a client mode: it imports neither the server nor the inventory engine, as
`mb-idri` requires (`metab --version` takes about 0.4 s today, so startup is the budget
to measure against).

1. **Resolve.** Classify TARGET exactly as ROOT is classified today: a local folder, a
   local file (its folder and selection), or a source URL with a selection.
   `--path` keeps its meaning.
   Nothing is cloned or fetched while resolving.
2. **Choose.** Read the preference (below) and detect the app.
   The result is `app`, `browser`, or a refusal.
3. **Deliver to the app:** `open -b <bundle> TARGET`, where TARGET is the absolute path
   or the normalized URL. Success means LaunchServices accepted it, not that a window
   showed it, and the report says so.
   What the app cannot take in Phase 1 (a local root with a non-file selection such as
   `/commit/…` or `#anchor`) goes to the browser, and the report says why.
4. **Deliver to a browser:** today’s path, a server started detached with the browser
   opened once it answers, so the agent need not hold a background process.
   Until host mode’s idle exit (`mb-qzny`) ships, the report names the pid and how to
   stop it.
5. **Report.** One line by default, and with `--json` an object with the resolved root,
   the selection, `delivered_to` (`app`, `browser`, or `none`), whether delivery is
   confirmed, the URL when there is one, and a reason code when it fell back or failed.
   Exit 0 when delivered; distinct codes, added to `cli/exit_codes.py`, for “blocked”
   (LaunchServices refused, as in a sandbox) and “app required but missing”.
   When blocked it prints the command for the user to run and never claims to have shown
   anything.
6. **Dry run.** `--present --dry-run --json` stops after step 2 and prints the plan.
   The app’s Open Location… sheet uses it to validate input, so the app parses no URL
   itself, and the goldens pin every target kind through it.

### The Preference

- `open_in: auto | app | browser` in `config.yml`, the user-owned configuration
  (`cache/records.py` `ApplicationConfig`), overridden by `METABROWSER_OPEN_IN` and
  `--open-in`.
- `auto` (the default) uses the app on macOS when detection finds it, and a browser
  otherwise; `app` refuses with its own exit code when the app is missing; `browser`
  never uses the app.
- The same choice governs a bare `metab PATH` only if the owner says so
  ([Open Questions](#open-questions)); any flag that shapes the server (`--no-open`,
  `--port`, `--host`, `--remote`, `--plugins-dir`, and the rest) keeps today’s
  serve-and-open behavior, because the app passes no flags to its servers.
- `--doctor --json` reports the resolved preference, its source, and what detection
  found.

### Detecting the App

Ask LaunchServices for the release bundle identifier through `ctypes`
(`LSCopyApplicationURLsForBundleIdentifier` in CoreServices): authoritative, a few
milliseconds, and no new dependency.
Spotlight (`mdfind`) is not used because it may be off or exclude the location;
`open -R` reveals the app in Finder; `osascript` is slow and can raise an automation
prompt. The dev bundle is used only when chosen explicitly.
Detection sits behind a seam the CLI tests replace, so the goldens cover every
combination on Linux CI.

### GitHub URLs in the App

Built in a different shape, which [Progress](#progress) summarizes and
[GitHub Links](../../architecture/arch-macos-app.md#github-links) describes; the design
as written on 2026-11-17 follows.

- **Entry.** `AppDelegate.request` accepts `https` URLs as well as file URLs, from
  `open -a`/`open -b` and from File > Open Location…, a sheet with one field that takes
  a GitHub URL or a local path and validates it with `--present --dry-run --json`. An
  unsupported URL shows `metab`’s own reason instead of being dropped.
- **Root identity.** A session is keyed by a `RootIdentity` that is either a canonical
  local path or a source (the canonical repository URL `metab` reports) with its pin.
  The local-path assumptions listed in Background move behind it: the session map, log
  names, the pre-ready title, saved tabs, and the folders waiting for a runtime.
- **Which window.** A target whose repository and pin match an open session joins it and
  navigates to the target’s address; otherwise a new session starts
  `metab URL --no-open --exit-on-eof`, so the cache, clone, size guard, and pin are
  `metab`’s. Whether a pull request page needs a server of its own pin is
  [Open Question 1](#open-questions).
- **Progress and failure.** The status view shows the clone report `metab` writes to
  stderr while the server is not yet ready, and a failure shows its reason code and the
  step that fixes it, with Retry.
- **Recents and restore.** A saved tab records a source root as its URL and pin; restore
  starts it only when its tab is shown, like a protected folder.
  Open Recent lists only file URLs (`NSDocumentController`), so source roots get their
  own section from the saved session until the roots route (`mb-a5ru`) lists them.

### Sign-In

- **One report, three readers.** `metab` gains a GitHub status check that runs
  `gh auth status --active --hostname github.com --json hosts` and reports the `gh` path
  and version, the active account, and a `GhFailureState`, through `--doctor --json` and
  a registered route, so the page, the app, and goldens read the same states.
  The app never runs `gh` itself.
- **Before the work.** `metab URL` and `--present URL` check sign-in before a first
  clone or a pull request read, and a failure stops with the reason and the command
  (`gh auth login --hostname github.com`, or the install link) instead of falling back
  silently. A public repository still opens anonymously without `gh`; the check only
  explains.
- **In the app.** A failure state shows the command with a Copy button, as the `metab`
  setup steps do (`SetupGuide`), and Retry; the app re-reads the status when it becomes
  active, so returning from Terminal after signing in clears the state.
- **Scopes.** The check reads the token’s scopes where `gh` reports them, so a private
  repository that fails for a missing `repo` scope says so rather than
  `not_found_or_private`.

### Named Commands (Phase 2)

- **A catalog in Python.** Command metadata (id, group, copy, scope, whether it takes a
  target) moves to a Python table served in `METABROWSER_SETTINGS`, as `keymap.py`
  serves reserved keys; the JavaScript registry binds handlers to those ids and fails
  its session test on any id without a row or row without a handler.
  `/api/commands` lists the catalog, so `--api /api/commands` and a golden pin it.
- **Names.** `<area>.<noun>[.<verb>]`, keeping the shortcut registry’s ids
  (`shell.home`, `main-tabs.pulls`, `pulls.open`), with plugin commands under the
  plugin’s name, and app menu commands under `app.` so the catalog can list what only
  the app does without the server running them.
- **Invoke.** A `present` request carries an address and optionally one command id with
  arguments; the page that receives the `navigate` event runs it through `invoke`, and
  the reply says whether its scope and target were live.
- **Addresses first.** Anything a URL can name is presented by address, not by command;
  `_mb_view` puts the view tab in the URL so it joins them.

## Implementation Plan

### Phase 1: Present Anything, and GitHub URLs in the App

Release-scoped. Each item is a bead under this plan; `mb-idri` keeps the Phase 2
transport.

- [ ] `metab TARGET --present` as a client mode: resolution, the report, `--json`,
  `--dry-run`, browser delivery with a detached server, and the new exit codes.
  Landed in jlevy/metabrowser#540 except browser delivery, with `--format json` for
  `--json`. Remaining: browser delivery (`mb-kze0`).
- [ ] The `open_in` preference in `config.yml`, `METABROWSER_OPEN_IN`, and `--open-in`,
  with `--doctor` reporting it.
  Remaining (`mb-gh6l`).
- [x] App detection through LaunchServices, and delivery by `open -b`, with the blocked
  and missing-app outcomes.
  Landed in jlevy/metabrowser#540, release identifier first and then dev.
- [ ] GitHub status: the check, its `--doctor` section and route, the check before a
  first clone or pull request read, and token scopes.
  Remaining (`mb-si2g`).
- [x] Map `/pull/N/files#diff-<hash>` to `/pull/<n>/files/<path>`, and open a commit URL
  at `/commit/<sha>`. The commit URL landed in jlevy/metabrowser#540, and the anchor in
  jlevy/metabrowser#574.
- [x] App: `RootIdentity` replaces the local-path key everywhere a session, log, title,
  saved tab, or waiting folder uses one.
  Landed in jlevy/metabrowser#539 as `SessionRoot`, keyed by repository without the pin;
  a saved tab still names a folder, since repository tabs are not saved.
- [x] App: accept `https` URLs in `AppDelegate.request`; show `metab`’s reason for any
  URL it refuses. Landed in jlevy/metabrowser#539, for GitHub links.
- [x] App: File > Open Location… with validation through `--present --dry-run --json`.
  Landed in jlevy/metabrowser#560 as File > Open URL…, for GitHub URLs only.
- [ ] App: clone progress and GitHub failure states in the status view, with Copy and
  Retry, and recheck on activation.
  Remaining (`mb-m0ry`).
- [ ] App: saved tabs and a recents section for source roots.
  Recents landed in jlevy/metabrowser#546 as `metab`’s recent targets.
  Remaining: saved tabs (`mb-682q`).
- [x] Skill: “Hand the User a Page” becomes `--present`, keeping the `--no-open` server
  for when it reports a browser fallback is not wanted; document the sandbox settings
  (Claude Code `excludedCommands`, Codex prefix approval).
  This is `mb-ko5d`’s Phase 1 part.
  Landed in jlevy/metabrowser#562.
- [x] Docs: [command line](../../../command-line.md), [the app](../../../macos-app.md),
  [the app’s architecture](../../architecture/arch-macos-app.md), and
  [the CLI architecture](../../architecture/arch-cli.md).
  Each describes what has landed; each remaining item updates them in its own change.

### Phase 2: Round Trip, Live Pages, and Named Commands

Builds on the native app plan’s Phase 3 beads, which keep their scope.

- [ ] `--present` delivers through the `metabrowser://` rendezvous (`mb-rtgh`) and the
  live-server registry (`mb-5xi4`), so the app replies with the window and URL, a page
  already open navigates (`mb-54r1`), local route addresses reach the app, and a new
  root waits for the in-app confirmation.
- [ ] The command catalog, `/api/commands`, and the handler-coverage session test.
- [ ] `present` carries a command id, and the reply reports what ran.
- [ ] `_mb_view` puts the view tab in the URL.

## Testing Strategy

- **Goldens:** `--present --dry-run --json` for every target kind (folder, file,
  `--path`, each GitHub shape, refused shapes, the shorthand) against each preference
  and detection result; `--present` delivery with a recording stand-in for `open`;
  `--doctor --json`’s GitHub and preference sections against fixture `gh` outputs for
  each `GhFailureState`.
- **Unit:** the LaunchServices binding on macOS CI; the exit-code mapping; the anchor
  mapping against GitHub’s published hash of a path.
- **Swift:** `RootIdentity` keying, saved-session reading of both kinds, and the Open
  Location sheet’s states, in `ShellCoreTests`; `LiveMetabTests` opening a `file://`
  repository URL end to end with no network.
- **Manual matrix** on a clean account, recorded in a QA document: CLI only, app only,
  both; `open_in` each way; a sandboxed agent; `gh` missing, signed out, signed in
  without access, and signed in; a public and a private repository, a pull request, a
  file, and a commit, each from the CLI, `--present`, `open -a`, and Open Location….

## Rollout Plan

Phase 1 ships with the first app release if the owner places it in the 0.13 epic
(`mb-wzsl`); otherwise in the next.
The app needs the `metab` that has `--present --dry-run`, so the app’s commit raises
`MetabRequirement.minimumRelease`, as AGENTS.md asks.
`CHANGELOG.md` notes `--present`, `open_in`, the exit codes, and the app’s new entry
points.

## Open Questions

Questions 1, 2, 5, and 6 are answered; 3 and 4 wait for the owner.

1. **Window identity for a repository.** One window per repository and pin, or per
   repository? Pull request pages may not depend on the pin, in which case a pull request
   URL could join any window of its repository.
   Recommendation: per repository and pin for `/view/`, and verify before deciding the
   pull request case. **Answered** on 2026-11-17 in bead `mb-87j0`: one window per
   repository, never keyed by the pin, and, by the owner’s decision recorded there, a
   link naming another branch, commit, or pull request head switches that window to the
   link’s revision. Built in jlevy/metabrowser#539.
2. **An open checkout of the same repository.** Should a GitHub URL join an open window
   of a local checkout whose `origin` is that repository, which already has the Pulls
   tab? Recommendation: yes for pull request URLs, no for file URLs at another ref.
   **Answered** by the owner on 2026-11-18, against the recommendation: a URL always
   opens the mirror. When a checkout of its repository is known, Open URL… is to offer
   “borrow from the checkout” or “open the checkout instead”
   ([The File Menu](../../architecture/arch-open-modes.md#the-file-menu)). The mirror is
   built (jlevy/metabrowser#560); the offer is not (`mb-bkk2`).
3. **New local roots from an agent in Phase 1.** `open -a` admits any folder today, so
   an agent’s `--present` could raise a privacy prompt in the app’s name.
   Accept that for the first release, or send roots the app does not have open to the
   browser until Phase 2’s confirmation?
   **Open.** As built, `--present` hands any folder to the app, which opens it as Open
   Folder… would; with no browser delivery yet, there is nowhere else to send it.
4. **Bare `metab PATH`.** Should it follow `open_in` and hand off to the app, exiting at
   once with a one-line message?
   Recommendation: yes, when no server-shaping flag is given.
   **Open**, and waits on `open_in` (`mb-gh6l`).
5. **Shorthand.** Accept `owner/repo` and `owner/repo#N` in `--present` and Open
   Location…, where no local path of that name exists?
   **Answered** by the owner on 2026-11-18 (bead `mb-m4mg`): no shorthand in the first
   release, only full GitHub URLs.
   Open URL… refuses one with its own message, and `--present` reads it as a local path.
6. **Shortcut for Open Location….** Command-L, as browsers use it, or Shift-Command-O?
   **Answered** by the owner on 2026-11-18 (bead `mb-m4mg`): Command-L, which was free.
   Built in jlevy/metabrowser#560.

## References

- [Native macOS app plan](plan-2026-11-10-native-macos-app.md), Phase 3 and 4
- [Server topology brief](../../research/research-2026-11-10-native-app-server-topology.md)
- [Open a repository from a Git URL](plan-2026-08-11-open-repo-from-git-url.md) and
  [pull request mirror and checkout](plan-2026-11-02-pr-review-mirror-and-checkout.md)
- [Menu primitives and file actions](plan-2026-08-06-menu-primitives-and-file-actions.md)
- [Functional UI and CLI parity](plan-2026-09-10-functional-ui-cli-parity.md)
- [Publishing the macOS app](plan-2026-11-16-macos-app-publishing.md)
- `skills/metabrowser/SKILL.md`

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
