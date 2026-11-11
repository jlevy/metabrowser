# Research: Setup Flows for `metab` and the Native macOS App

**Date:** 2026-11-11

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete

Extends [Native macOS App for Metabrowser](research-2026-11-08-macos-app-packaging.md)
(2026-11-08), which settles the shell, the uv runtimes, signing, notarization, the cask,
and Sparkle, and
[Server Topology, Lifecycle, and Agent Handoff](research-2026-11-10-native-app-server-topology.md)
(2026-11-10).

## Overview

A user reaches a working Metabrowser on a Mac in one of two standard ways:

- **Flow 1, CLI first:** `uv tool install metabrowser`, then the app installed the
  normal way, from the DMG on GitHub Releases dragged to Applications or from the
  Homebrew cask.
- **Flow 2, app first:** the user downloads and opens the app with no `metab` installed.

Both should end cleanly: the app finds `metab` without help, works with the version it
finds or says exactly what to run, and leaves an installation the user can update and
remove. This brief walks both flows through the spike in `apps/macos/` (branch
`claude/macos-app-spike`), names where each can go wrong, measures the cold install that
Flow 2 depends on, and chooses a first-run design.
A later, optional convenience, `metab` installing the app itself, gets a short section
at the end.

The app is a thin AppKit and `WKWebView` shell over the `metab` CLI, which stays the
product. Dev and release builds have separate bundle ids,
`io.github.jlevy.metabrowser.dev` and `io.github.jlevy.metabrowser`.

## Summary

- **Flow 1 already works in the spike.** `uv tool install metabrowser` puts `metab` in
  `~/.local/bin`, and the app finds it there with a file check; a Finder-launched app
  has no shell `PATH`, and does not need one.
  The gaps:
  - the app requires no version;
  - it does not notice `uv tool upgrade`;
  - the first `metab --version` after an install took 3.3 s (0.35 s afterwards);
  - a copy run from the mounted DMG is translocated without a word.
- **Give the app a version policy.** One required minimum, below which the app shows the
  exact upgrade command and starts nothing.
  Graceful fallbacks above it: the folder identity route’s 404 fallback is the pattern.
  After an upgrade, restart servers rather than run new code in old processes.
  The host-protocol version replaces the minimum once host mode exists.
- **Flow 2 today stops at a copyable `uv tool install metabrowser`,** which assumes uv
  is installed and needs a manual Find Again.
- **Recommended Flow 2:**
  - **(i) Now:** show only the missing steps (install uv, install `metab`) as copyable
    commands, and detect the result without a Find Again click.
  - **(ii) Next:** an “Install for me” button that runs the user’s uv, or a signed uv
    inside the app, to do the documented `uv tool install`. The result is exactly Flow
    1’s installation, so the user also gets a terminal `metab`.
  - **(iii) Narrowed:** the app-private, hash-pinned runtime (`mb-lrcd`) becomes an
    optional mode for offline and locked-down Macs, built only on demand.
- **The cold path is short and fails cleanly.** Measured with uv 0.12.8 and nothing
  cached:
  - `uv tool install metabrowser` took 13.8 s, 25 MiB of it a CPython download;
  - with the cache warm it took 0.22 s;
  - with the network unreachable it failed in 8.8 s and left no `metab`;
  - no installed file carried `com.apple.quarantine`.
- **uv’s receipt is hidden policy.** Whatever an installer passes (an exact pin, a fixed
  `--exclude-newer` date) is recorded and governs every later `uv tool upgrade`, so
  “Install for me” must pass no more than the documented command plus a version floor.
- **The risks for (ii) and (iii) are platform bugs, not uv usage.** On a Mac without the
  Command Line Tools, uv’s managed-Python install can raise the developer-tools dialog
  ([uv#14893](https://github.com/astral-sh/uv/issues/14893), open), and some Macs kill
  uv’s ad hoc Python ([uv#16726](https://github.com/astral-sh/uv/issues/16726), open).
  Only (iii) has a fallback for the second.
- **`metab` installing the app is a later option (`mb-92d9`),** after both flows are
  clean. Its findings are kept below in short form.

## Questions to Answer

1. What does Flow 1 look like end to end, and where can it go wrong?
2. Which `metab` versions should the app accept, and how does it say so?
3. What should happen when the app finds no `metab` (Flow 2)?
4. Which first-run design: commands, “Install for me”, or the app-private runtime?
5. What are checkable criteria for “works cleanly”?
6. Later: should `metab` install the app?

## Scope

**In scope:** arm64 Macs on macOS 15 and later; both variants; installing uv and
`metab`, installing the app by DMG or cask, first launch, version skew, upgrades,
repair, and removal; the cold install’s time, network, and failure behavior.

**Out of scope:** the shell itself, signing, notarization, and the runtime builder (the
2026-11-08 brief); server topology and the agent front door (the 2026-11-10 brief);
Windows and Linux; the Mac App Store.

## Terms

- **CLI install:** `metab` installed by `uv tool install metabrowser`, in uv’s standard
  locations. The earlier brief’s **app-managed runtime** is one the app builds in its own
  Application Support folder.
- **Tool receipt:** `uv-receipt.toml` in a tool’s environment, where uv records the
  requirement and settings a tool was installed with.
- **Quarantine:** the `com.apple.quarantine` attribute that makes Gatekeeper assess a
  file when it is first opened.
  **App Translocation** is Gatekeeper running a quarantined app that was not moved from
  its download location from a randomized read-only path.
- **Designated requirement (DR):** the code-signing rule that says which later builds
  count as the same program; privacy (TCC) grants are recorded against it.

## Findings

### Flow 1 Today: CLI First

The spike’s discovery and first-run code was read at `8d2b87d6`
(`Sources/ShellCore/Runtime/RuntimeDiscovery.swift`, `Runtime.swift`,
`Sources/Metabrowser/RuntimeWindow.swift`, `AppDelegate.swift`).

| Step | What happens | Where it can go wrong |
| --- | --- | --- |
| 1. Install uv | the official installer (`curl … \| sh`) puts uv in the user executable directory, the same one `uv tool install` uses, and may add it to the shell profiles unless `UV_NO_MODIFY_PATH` is set ([installer docs](https://github.com/astral-sh/uv/blob/0.13.7/docs/reference/installer.md)); or `brew install uv` | after `brew install uv`, nothing adds the tool directory to `PATH`; see step 2 |
| 2. `uv tool install metabrowser` | the environment goes in `uv tool dir` (`~/.local/share/uv/tools`) and the `metab` link in `uv tool dir --bin` (`~/.local/bin`) (measured); Python is an existing 3.12 or later found on the system, or a uv-managed download ([Python versions](https://github.com/astral-sh/uv/blob/0.13.7/docs/concepts/python-versions.md)) | `~/.local/bin` is not on macOS’s default `PATH` (`/etc/paths`), so Terminal says `metab` is not found until `uv tool update-shell`, which for zsh adds it in `~/.zshenv` (measured in a scratch home). A Homebrew Python found first binds the tool to it, and a later `brew upgrade python` can break the environment (inferred) |
| 3. Install the app | a browser download of the DMG is quarantined; Gatekeeper checks the image, and the user drags the app to Applications. The cask downloads the same DMG, quarantines it, and moves the app into `/Applications` ([Homebrew quarantine](https://github.com/Homebrew/brew/blob/7.0.13/Library/Homebrew/cask/quarantine.rb#L127-L134)) | an app opened straight from the DMG or Downloads is translocated on first launch ([Packaging Mac software](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution)); it works but cannot be updated in place later (Sparkle refuses such copies, [source](https://github.com/sparkle-project/Sparkle/blob/2.10.1/Sparkle/SPUBasicUpdateDriver.m#L71-L80)), and the spike does not detect it |
| 4. First launch | Gatekeeper asks once whether to open an app downloaded from the Internet, noting Apple checked it ([Apple](https://support.apple.com/en-us/102445)); the cask’s copy is quarantined too, so it should ask the same (inferred from Homebrew’s code) | none for a notarized release; a dev or rehearsal build is ad hoc–signed and refused on any other Mac |
| 5. Discovery | the saved path, `METABROWSER_METAB`, `~/.local/bin/metab`, uv’s tool bin directory, `/opt/homebrew/bin`, and `/usr/local/bin` each cost a file check and one `metab --version`; the login shell runs only when `metab`, `git`, or `gh` is still missing | the first `metab --version` after an install took 3.31 s (bytecode compilation and first imports), later ones 0.35 s (measured); consulting the login shell runs the user’s startup files in the app’s name, which can take seconds and raise privacy prompts (the spike’s own comment) |
| 6. First folder | the app spawns `metab` as its child, so privacy prompts name the app (2026-11-10 brief) | `metab` 0.12.0, the current release, has no `/api/identity`; the window falls back to the folder’s path (`FolderSession.swift`) |
| 7. Later launches | the saved runtime is checked only for being an executable file, costing no subprocess (`Runtime.swift`) | a `uv tool upgrade` goes unnoticed: the app accepts whatever version is there |
| 8. Removal | `uv tool uninstall metabrowser`; the app to the Trash or `brew uninstall --cask` (the cask’s `zap` list removes its data) | `metab`’s own state in `~/.cache/metabrowser` and `~/.config/metabrowser` stays until removed by hand |

Two alternatives for the CLI step exist but are not the standard path.
The cask could declare `depends_on formula: "uv"`, which the
[Cask Cookbook](https://github.com/Homebrew/brew/blob/7.0.13/docs/Cask-Cookbook.md)
supports. But official casks may run only structured flight steps, not commands, so the
cask cannot run `uv tool install` itself; a personal tap could do so only through legacy
Ruby blocks, which Homebrew keeps “temporarily”.
A Homebrew formula for `metab`, for which the cask template reserves the name, would be
found by discovery in `/opt/homebrew/bin`.

### Version Skew Between the App and `metab`

- **The spike accepts any `metab` that prints `metab X`.** `RuntimeDiscovery.validate`
  parses the version and checks nothing else, and later launches skip even that.
- **The identity route shows the pattern for fallbacks.** The app asks
  `GET /api/identity`; on a 404 from a `metab` older than the route it names the window
  from the folder’s path and logs why (`FolderIdentity.swift`, `FolderSession.swift`).
  That is right for a cosmetic feature and wrong for a contract the app cannot work
  without, such as the host protocol.
- **The earlier brief already names the rule for the hard case:** a CLI install updates
  independently of the app, so the host protocol is a versioned boundary answered with
  VERSION + FAIL FAST, and the app accepts exactly one protocol version.
- **Upgrades under running servers.** `uv tool upgrade` rewrites the environment that
  live servers import from; the earlier brief warns that this breaks their deferred
  imports, and the 2026-11-10 brief that a warm server outlives an upgrade.
- **The receipt keeps what the install asked for.** uv retains an install’s version
  constraints and settings on every `uv tool upgrade`
  ([uv tools](https://github.com/astral-sh/uv/blob/0.13.7/docs/concepts/tools.md)).
  Measured receipts recorded `metabrowser>=0.12` as the requirement, and either a fixed
  `exclude-newer` timestamp or, for `--exclude-newer "14 days"`, both a timestamp and
  `exclude-newer-span = "P14D"`. So the documented upgrade,
  `uv tool install --upgrade metabrowser==<version>`
  ([installation](../../installation.md)), pins that version for good, and a later bare
  `uv tool upgrade` will not move it (inferred from the docs).

### Dev and Release Variants

| Concern | Dev (`Metabrowser Dev.app`) | Release (`Metabrowser.app`) |
| --- | --- | --- |
| Signature | ad hoc; runs only on the Mac that built it | Developer ID, notarized and stapled |
| Privacy grants | keyed to an ad hoc requirement that matches one build only ([TN3127](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements)), so each rebuild prompts again | kept across updates from the same team |
| Defaults and saved runtime | its own defaults domain, so its own discovery result | its own |
| `metab` | any; `METABROWSER_METAB` or Choose metab… can point it at a checkout | the CLI install |
| LaunchServices | registered wherever it was built or launched (measured) | the same holds for release-variant rehearsal builds, which carry the release id (measured; `mb-nneo`) |
| Logs | `~/Library/Logs/Metabrowser`, shared with the release (a spike gap) | the same folder |

Both variants run the same CLI install; nothing in Flow 1 needs a variant-specific step.

### Flow 2 Today: App First, No CLI

With no saved runtime, the spike runs discovery, including the login shell, then shows
“Metabrowser needs the metab command-line tool” with `uv tool install metabrowser`, a
Copy button, a link to the installation guide, Find Again, Choose metab…, Run Doctor,
and Reveal Logs (`RuntimeWindow.swift`). It does not check for uv, so a user without uv
copies a command that fails, and nothing notices when `metab` appears.

### The Cold Path, Measured

Run with uv 0.12.8 on an arm64 Mac with macOS 26.5.2, from a cleared environment with
`--no-config`, a scratch `HOME`, and `UV_TOOL_DIR`, `UV_TOOL_BIN_DIR`, `UV_CACHE_DIR`,
and `UV_PYTHON_INSTALL_DIR` all in a new scratch directory, so nothing was cached.
`UV_MANAGED_PYTHON=1` stood in for a Mac with no Python 3.12. The cool-off was applied
with `--exclude-newer 2026-10-28T00:00:00Z`, exempting the first-party `metabrowser`
(0.12.0, published 2026-11-09). The link speed was not measured.

| Probe | Result |
| --- | --- |
| Cold `uv tool install metabrowser` | 13.8 s wall: CPython 3.14.7 downloaded from GitHub (25.3 MiB), 46 packages resolved in 1.89 s, prepared in 1.28 s, installed in 150 ms. On disk: 68 MB of Python, 38 MB of tool environment, 47 MB of cache |
| First `metab --version` | 3.31 s, then 0.35 and 0.36 s |
| Warm cache, new tool directory | 0.22 s online, 0.13 s with `--offline` |
| Offline with an empty cache | fails in 0.04 s: no managed interpreter, and downloads are off |
| Network unreachable (a proxy that refuses) | fails after 3 retries in 8.8 s, naming the Python download URL; no `metab` link and no tool environment were created |
| Quarantine | 0 files with `com.apple.quarantine` in the tool environment, the Python, or the cache; native extensions are ad hoc–signed |
| `uv tool update-shell` with zsh | created `~/.zshenv` with `export PATH="$HOME/.local/bin:$PATH"` (spelled out as an absolute path) |

Earlier probes on the same Mac also bear on both flows:

- A `curl` download carried `com.apple.provenance` but no quarantine; so did a file made
  with `touch`, so provenance marks the writing process, not a download.
- Of 151 apps in `/Applications`, 53 carried quarantine.
  Apps whose attribute names a browser mostly had flags `01c1` or `0181`, and the two
  cask-installed apps had `0381` and `03c1`; 49 of the 53 set bit 0x0100, which
  Homebrew’s code calls the translocation bit.
- A read-only LaunchServices query by bundle id took about 0.09 s and resolved both
  variants’ ids to build folders inside repository checkouts.

### What Other Apps Do at First Run

- **Python desktop apps** (from the 2026-11-08 brief’s survey): Positron uses the user’s
  interpreters and installs uv only with consent; Open WebUI Desktop downloads Python
  and then uses uv; Anki shipped a uv first-run launcher and replaced it with Briefcase,
  citing a Terminal window, the developer-tools prompt, inherited configuration, and no
  offline install ([anki#5019](https://github.com/ankitects/anki/pull/5019)).
- **Apps that set up their CLI:**
  - VS Code, Ollama, and JupyterLab Desktop link a command into `/usr/local/bin` behind
    an administrator prompt
    ([VS Code](https://github.com/microsoft/vscode/blob/1.146.0/src/vs/platform/native/electron-main/nativeHostMainService.ts#L551-L640),
    [Ollama](https://github.com/ollama/ollama/blob/v0.40.16/app/cmd/app/app_darwin.m#L2236-L2300),
    [JupyterLab Desktop](https://github.com/jupyterlab/jupyterlab-desktop/blob/v4.6.3-1/src/main/utils.ts)).
  - Zed’s installer links `~/.local/bin/zed` with no prompt
    ([install.sh](https://github.com/zed-industries/zed/blob/v1.27.0/script/install.sh#L153-L171)).
  - LM Studio’s `lms bootstrap` appends to the user’s shell startup files
    ([bootstrap.ts](https://github.com/lmstudio-ai/lms/blob/138dcffbc40e5fe3d9c0d38cf75dcdc1d883d849/src/subcommands/bootstrap.ts)).
- **Tool installers:** neither uv nor pipx creates app bundles or launchers; pipx closed
  desktop integration as out of scope
  ([pipx#717](https://github.com/pypa/pipx/issues/717)), and uv’s maintainers oppose
  install-time hooks ([uv#12750](https://github.com/astral-sh/uv/issues/12750)).

### macOS Behaviors That Matter Here

- **Downloads by a child process are not quarantined** unless the app opts in with
  `LSFileQuarantineEnabled`, which the spike deliberately omits (its `Info.plist` and
  the earlier brief); `curl` and uv set nothing (measured;
  [DTS](https://developer.apple.com/forums/thread/706442)). Files “Install for me”
  writes therefore never trigger Gatekeeper.
- **Privacy attribution:** the app is the responsible process for children it spawns
  ([DTS](https://developer.apple.com/forums/thread/678819)), so a uv it runs is charged
  to the app. uv writes only under `~/.local` and `~/.cache`, which TCC does not protect,
  so the install should raise no prompt (inferred).
  PyPI and GitHub are not on the local network, so no Local Network prompt either
  (inferred from
  [TN3179](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy)).
- **A Finder launch gets almost no environment:** no shell `PATH`, no proxy variables,
  and no `UV_*` settings exported from shell startup files (the spike’s comment in
  `RuntimeDiscovery.swift`). The spike passes proxy variables through to children only
  when the app itself has them.
- **Translocation** applies to a quarantined app opened without being moved, on first
  launch only; DTS knows no supported way to detect it
  ([DTS](https://developer.apple.com/forums/thread/724969)).

## Key Insights

- **Both flows should end in the same state:** one CLI install in uv’s standard
  locations, which the app finds with a file check.
  Flow 2 is then a front end for Flow 1, not a second install kind, and plugins,
  upgrades, and the terminal `metab` work the same either way.
- **The app never needs `PATH`; the user’s terminal does.** Discovery checks
  `~/.local/bin` directly.
  Putting `~/.local/bin` on `PATH` is a terminal convenience, offered with consent.
- **Version policy is a contract with an independently updated consumer.** It needs a
  required floor, graceful fallbacks above it, and the exact command to fix a mismatch.
- **uv’s receipt turns install flags into permanent policy,** so an app-run install must
  look like a user-run one.
- **A first install is network-bound but short:** about 14 s cold, sub-second warm, and
  a clean failure in under 10 s. That is acceptable once, behind a progress view.
- **The hard failures are platform bugs shared by (ii) and (iii)** (the developer-tools
  dialog and the SIGKILL). The app-private runtime’s real advantages are offline
  install, hash pinning, and a signed-Python fallback, not a better happy path.

## Options Considered

### Flow 2 First Run

|  | (i) Copyable commands | (ii) “Install for me” | (iii) App-private runtime (`mb-lrcd`) |
| --- | --- | --- | --- |
| Result | Flow 1’s CLI install, made by the user | Flow 1’s CLI install, made by the app | a second install kind in Application Support |
| Terminal `metab` | yes | yes, once `~/.local/bin` is on `PATH` (opt-in) | only through the earlier brief’s opt-in launcher |
| Consent | the user runs each command | one sheet: what is downloaded, from where, and where it goes | at first run |
| uv | the user installs it | the user’s uv when present and new enough, otherwise one signed inside the app (27.9 MB, per the earlier brief) | inside the app |
| Python | as Flow 1 | as Flow 1: an existing 3.12 or later, else a 25 MiB download | uv-managed, or a bundled archive for offline install |
| Integrity | PyPI and TLS, as Flow 1 | the same; `uv tool install` cannot check hashes today (earlier brief; [uv#21962](https://github.com/astral-sh/uv/issues/21962) open) | hash-pinned `pylock.toml` |
| Offline | no | no: fails in 8.8 s, cleanly | yes, with the bundled Python archive |
| Uses the user’s uv configuration | yes | yes, by design, so indexes and mirrors apply as in Flow 1 | no: isolated |
| New code | detection and copy text | a runner, a progress view, repair and removal | the runtime builder, environment lifecycle, plugin installs, and separate state homes |

**Answering the earlier brief’s objections to (ii).** The 2026-11-08 brief rejected
“delegating to the CLI installer” for three reasons:

1. **Not an ordinary CLI install:** its app’s uv was isolated to app-owned directories.
   Here the uv deliberately writes uv’s standard locations, and the user’s own uv is
   preferred when one exists.
2. **No cool-off:** the documented Flow 1 command has none either, and a CLI install
   follows the user’s configuration by that brief’s own rule.
   Adding flags is worse: the receipt would keep them for every later upgrade.
3. **uv#14893 and uv#16726, with no signed-Python fallback:** still true.
   They gate (ii) on a clean account without the Command Line Tools (below), and they
   are the reason to keep (iii) available.

**Rejected variants of (ii):**

- **Download uv on demand** instead of bundling it, with a check against Astral’s
  Developer ID: saves about 28 MB, but adds a network dependency at the worst moment.
- **A cask postflight that runs the install:** see Flow 1; Homebrew would own an app
  whose runtime it does not track.

### Later: `metab` Installs the App

Once both flows are clean, a `metab` mode could install the app for users who start in
Terminal: `uvx metabrowser <install mode>` would then reach the real app in one command
(`mb-92d9`, with `mb-5jr9` and `mb-56nq`). What the first version of this brief found,
kept in short form:

- **No precedent with uv.** No project uses uv or pipx to install a Mac app; uv and pipx
  have scoped desktop integration out, and wheels have no install hooks
  ([uv#13729](https://github.com/astral-sh/uv/issues/13729),
  [pipx#717](https://github.com/pypa/pipx/issues/717),
  [wheel format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/)).
  Packages that place apps generate unsigned or ad hoc launchers from their own CLI:
  [Photini](https://github.com/jim-easterbrook/Photini/blob/91294af071ad8387bc746ee3ec773589710efdd4/src/photini/macos.py),
  [menuinst](https://github.com/conda/menuinst/blob/2.5.2/menuinst/platforms/osx.py),
  `pixi global`, and
  [Claude Code’s URL handler](https://code.claude.com/docs/en/deep-links).
  kitty’s and Zed’s shell installers copy a notarized app into `/Applications` and
  verify nothing
  ([kitty](https://github.com/kovidgoyal/kitty/blob/v0.50.0/docs/installer.sh)).
- **No quarantine, so the installer verifies.** A command-line download is never
  quarantined, so there is no prompt and no translocation.
  macOS 13 and later still check a notarized app’s integrity at first launch
  ([WWDC22 10096](https://developer.apple.com/videos/play/wwdc2022/10096/)), but
  identity is the installer’s job.
  The base-OS checks took 0.5–0.9 s each on a notarized app:
  `codesign --verify --strict` with a requirement pinning the Team ID, and
  `codesign -R=notarized --check-notarization` (measured).
  `stapler` is an `xcode-select` shim, unavailable without developer tools (measured).
- **Copy, then replace whole.** Symlinked apps are invisible to Spotlight
  ([brew#1808](https://github.com/Homebrew/brew/pull/1808),
  [nix-darwin#1396](https://github.com/nix-darwin/nix-darwin/pull/1396)). App bundle
  protection blocks writes inside a launched app by other teams’ processes, Terminal
  included; DTS advises staging a complete copy and moving it into place
  ([DTS](https://developer.apple.com/forums/thread/779326)). Rename and delete of a
  whole launched bundle from Terminal is unsettled.
- **Find the app by bundle id, filtered.** LaunchServices returns every registered copy,
  build folders included (measured); a fixed-path check misses `~/Applications`
  ([claude-code#41899](https://github.com/anthropics/claude-code/issues/41899)).
- **Rejected carriers:**
  - A wheel holding the app breaks the bundle’s seal at the first symlink (measured),
    and Sparkle’s framework needs symlinks.
  - A generated launcher is not the Swift shell, and an ad hoc one loses its privacy
    grants whenever it is regenerated.
- **One owner per copy:** Homebrew for a cask install, `metab` for its own, and Sparkle
  for both once it ships, with the cask declaring `auto_updates true`
  ([cask.rb](https://github.com/Homebrew/brew/blob/7.0.13/Library/Homebrew/cask/cask.rb#L477-L497)).

## Recommendations

1. **Make Flow 1 the documented standard.** Add the app to
   [Installation](../../installation.md) after `uv tool install metabrowser`: the DMG or
   the cask, Applications rather than the DMG, and `uv tool update-shell` for the
   terminal. The app needs nothing on `PATH`.
2. **Give the app a version policy:**
   - **A required minimum** (later, the one host-protocol version), checked when a
     runtime is found and before each server start.
     Below it, start nothing; show the version found, the version needed, and
     `uv tool install --upgrade metabrowser==<tested version>`, matching the
     installation guide’s reviewed-release rule, with a Copy button.
   - **Feature fallbacks above it,** like the identity route’s 404 handling, each
     logged.
   - **Notice upgrades.** Recheck the version when a folder opens if the runtime’s
     executable or environment changed, and offer to restart running servers instead of
     letting them import new code.
3. **Flag a translocated or disk-image launch** on first run with a “Move to
   Applications” notice.
   There is no supported detection API, so use a path heuristic, a read-only volume or
   an `/AppTranslocation/` path, as Sparkle does.
4. **Ship Flow 2 (i) with the next spike change:** check for uv (`~/.local/bin/uv`, the
   Homebrew prefixes, then the login shell), show only the missing commands, and watch
   `~/.local/bin` so the app continues by itself when `metab` appears.
5. **Build Flow 2 (ii) next,** as a button beside the commands:
   - Prefer the user’s uv when it is at least the tested version; otherwise run the
     signed uv inside the app.
   - Run exactly `uv tool install 'metabrowser>=<minimum>'`, honoring the user’s uv
     configuration, from a cleared environment that keeps proxies, as the spike does for
     servers.
   - Consent, progress, and failure: a sheet naming the downloads (Python from GitHub,
     packages from PyPI), sizes, and destinations, with an opt-in “Add `metab` to my
     terminal” that runs `uv tool update-shell`. Stream uv’s output into a progress
     view. On failure, show uv’s last lines, Retry, and the command to run by hand.
   - Repair and removal: Settings offers Reinstall (`uv tool install --reinstall`) and
     Remove (`uv tool uninstall metabrowser`) for an install the app made, and says that
     the Python and the cache stay in uv’s folders.
6. **Narrow `mb-lrcd` to (iii) as an optional mode** for offline, managed, or
   hash-pinned setups, built only when such a user appears.
   (ii) replaces it as the default answer for a Mac with no CLI, and the runtime builder
   leaves Phase 5’s critical path.
7. **Defer `metab` installing the app** (`mb-92d9`) until both flows pass their gates.

### CLI Parity

Finding a runtime and the first-run screen are already named shell-only exemptions in
the earlier brief, because no `metab` exists yet to ask; (i) and (ii) fall under them.
Their evidence:

- **`ShellCore` unit tests** with fake runners, for discovery, the version policy, uv
  detection, and the install runner’s states and failures;
- **a live test** that runs the real `uv tool install` into redirected scratch
  directories, as measured here, on a macOS CI job;
- **a QA playbook** for the parts only a real Mac shows: Gatekeeper, translocation, and
  the developer-tools dialog.

The version floor is a constant in the shell; `metab --version` and, later, the host
mode’s ready line supply the other side.
The later install mode keeps the parity rows its own bead needs (a status mode with
`--json` and a `--dry-run` plan, with goldens).

### Gates

- **Flow 1 end to end,** on clean macOS 15 and 26 accounts, one admin and one standard:
  uv from the official installer and from Homebrew; `uv tool install metabrowser`; the
  app from the DMG and from the cask.
  Every criterion under Falsifiable Claims 1, 4, and 5 holds.
- **Flow 2 (ii) on a clean account without the Command Line Tools:** if the
  developer-tools dialog appears (uv#14893), ship a workaround first or keep the button
  hidden and fall back to (i).

### Falsifiable Claims

1. **Flow 1:** after `uv tool install metabrowser` and dragging the release app to
   Applications, the first launch reaches the Open panel after one Gatekeeper prompt,
   with no runtime screen and no login-shell consult when `git` and `gh` come from
   Homebrew, in under 5 s.
2. **Flow 2 (ii), online:** from “Install for me” to the Open panel takes under 30 s on
   a connection like the one measured here (13.8 s install plus 3.3 s first run).
3. **Flow 2 (ii), offline:** the failure is reported within 15 s, and no `metab` link or
   tool environment is left behind (8.8 s measured).
4. **Same state:** an install made by (ii) has the same tool directory, link, and
   receipt as Flow 1’s apart from its version floor, and the user’s
   `uv tool upgrade metabrowser` works on it afterwards.
5. **Skew:** with a `metab` below the minimum, the app starts no server and shows the
   exact upgrade command.
   After a compatible upgrade, the next folder opened runs the new version, and no
   running server imports the new code.
6. **No quarantine:** no file written by either flow’s install carries
   `com.apple.quarantine`.

## Where This Breaks

- **Macs without the Command Line Tools:** uv’s managed-Python install calls
  `install_name_tool`, which can raise the developer-tools dialog (uv#14893). Anki
  shipped a no-op stub for it; the earlier brief records that workaround.
- **Managed Macs:** uv’s Python is sometimes killed (uv#16726), PyPI or GitHub may be
  blocked, and TLS interception needs uv’s system-certificate setting (earlier brief).
  These are the users (iii) is for.
- **Proxies set only in shell startup files** never reach a Finder-launched app; (ii)
  then fails where Terminal succeeds, so its failure view must offer the command.
- **A bundled uv and an older user uv:** a receipt written by the app’s uv may carry
  fields an older uv does not know (unsettled), which is one more reason to prefer the
  user’s uv.
- **Developers with several installs** (a checkout, `uvx`, a tool install) get whichever
  discovery finds first; Settings already shows which and lets them choose.

## Open Questions

- Does a cask install show the same first-launch prompt as a browser download?
  Homebrew’s code suggests it does; not observed here.
- Does uv’s managed-Python install still raise the developer-tools dialog on macOS 26
  and 27 without the Command Line Tools?
- Can an older uv read a tool receipt that a newer uv wrote?
- Does uv use macOS’s system proxy settings when no proxy variables are set?
- Which upgrade instruction should the app show: the installation guide’s exact pin,
  which a later bare `uv tool upgrade` will not move, or a floor?

## Next Steps

- [ ] Add the app to the installation guide as Flow 1.
- [ ] Track the version policy and the upgrade notice, Flow 2 (i), and Flow 2 (ii) as
  beads under `mb-1apq`, and re-scope `mb-lrcd` and the clean-account matrix (`mb-5fp7`)
  to match.
- [ ] Run the Flow 1 gate with the first Developer ID build (`mb-e9fm`).
- [ ] Probe uv#14893 on a clean account before building (ii).

## Methodology

The spike’s discovery, first-run, and identity code was read at `8d2b87d6`. The cold
install was measured in scratch directories with every uv location redirected and no
user configuration, then repeated warm, offline, and with the network refused;
`uv tool update-shell` ran against a scratch home.
Facts about uv come from its documentation and receipts at uv 0.13.7 and from the
installed 0.12.8. The first version of this brief contributed three parallel
source-reading tracks (Python packaging tools, apps and package managers, and Apple’s
documentation and DTS posts) and the local probes summarized above.
Nothing was written to an Applications folder, the LaunchServices database, or the
user’s shell files.

**Not tested:** a Developer ID build (none exists yet); a Mac without the Command Line
Tools; a standard account; macOS 15 or 27; a cask install of this app; “Install for me”
itself, which is not built.

## References

- Earlier briefs and plan:
  [Native macOS App for Metabrowser](research-2026-11-08-macos-app-packaging.md),
  [Server Topology, Lifecycle, and Agent Handoff](research-2026-11-10-native-app-server-topology.md),
  [Plan for the Native macOS App](../specs/active/plan-2026-11-10-native-macos-app.md)
- Repository: [Installation](../../installation.md),
  [Views, Models, and Routes](../architecture/arch-views-models-routes.md),
  [supply-chain policy](../../../SUPPLY-CHAIN-SECURITY.md); on the spike branch,
  `apps/macos/README.md`, `RuntimeDiscovery.swift`, `RuntimeWindow.swift`, and
  `apps/macos/packaging/metabrowser-app.rb.template`
- uv: [tools](https://github.com/astral-sh/uv/blob/0.13.7/docs/concepts/tools.md),
  [Python versions](https://github.com/astral-sh/uv/blob/0.13.7/docs/concepts/python-versions.md),
  [installer](https://github.com/astral-sh/uv/blob/0.13.7/docs/reference/installer.md),
  [uv#14893](https://github.com/astral-sh/uv/issues/14893),
  [uv#16726](https://github.com/astral-sh/uv/issues/16726),
  [uv#21962](https://github.com/astral-sh/uv/issues/21962),
  [uv#12750](https://github.com/astral-sh/uv/issues/12750),
  [uv#13729](https://github.com/astral-sh/uv/issues/13729)
- Packaging and installers: [pipx#717](https://github.com/pypa/pipx/issues/717),
  [wheel format](https://packaging.python.org/en/latest/specifications/binary-distribution-format/),
  [Cask Cookbook](https://github.com/Homebrew/brew/blob/7.0.13/docs/Cask-Cookbook.md),
  [Homebrew quarantine](https://github.com/Homebrew/brew/blob/7.0.13/Library/Homebrew/cask/quarantine.rb),
  [brew#1808](https://github.com/Homebrew/brew/pull/1808),
  [nix-darwin#1396](https://github.com/nix-darwin/nix-darwin/pull/1396),
  [Photini](https://github.com/jim-easterbrook/Photini),
  [menuinst](https://github.com/conda/menuinst),
  [kitty installer](https://github.com/kovidgoyal/kitty/blob/v0.50.0/docs/installer.sh),
  [Zed install.sh](https://github.com/zed-industries/zed/blob/v1.27.0/script/install.sh),
  [Claude Code deep links](https://code.claude.com/docs/en/deep-links),
  [anki#5019](https://github.com/ankitects/anki/pull/5019)
- Updates:
  [Sparkle](https://github.com/sparkle-project/Sparkle/blob/2.10.1/Sparkle/SPUBasicUpdateDriver.m#L71-L80),
  [Homebrew `auto_updates`](https://github.com/Homebrew/brew/blob/7.0.13/Library/Homebrew/cask/cask.rb#L477-L497)
- Apple:
  [Packaging Mac software for distribution](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution),
  [Safely open apps](https://support.apple.com/en-us/102445),
  [TN3127](https://developer.apple.com/documentation/technotes/tn3127-inside-code-signing-requirements),
  [TN3179](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy),
  [WWDC22 10096](https://developer.apple.com/videos/play/wwdc2022/10096/); DTS threads
  [706442](https://developer.apple.com/forums/thread/706442),
  [678819](https://developer.apple.com/forums/thread/678819),
  [724969](https://developer.apple.com/forums/thread/724969),
  [779326](https://developer.apple.com/forums/thread/779326)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
