# Research: Native macOS App for Metabrowser

**Date:** 2026-11-08

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Complete; its agent-controlled server questions are taken further, and its
per-instance cookie name corrected, in the
[2026-11-10 addendum](#2026-11-10-addendum-server-topology-and-agent-handoff); its
WebKit measurement gate was run, and failed, in the
[2026-11-11 addendum](#2026-11-11-addendum-the-webkit-measurement-gate)

Supersedes, for macOS,
[Desktop App Packaging for Metabrowser](research-2026-08-16-desktop-app-packaging.md)
(2026-08-16), which covered three platforms and recommended Electron.

## Overview

Metabrowser ships as a Python package: `uv tool install metabrowser` or
`uvx metabrowser@latest`, a local Starlette server, and whatever browser the user has.
This research evaluates how to offer it as a **native macOS app** that someone without
uv or Python can install from a DMG or Homebrew.
The shell should add as little code, size, and toolchain as possible while still giving
the affordances only an app has: a Dock identity, Open With, folder drops, and a URL
scheme.

Three requirements shape the design as much as the choice of shell:

- **`metab` stays the product.** Everything the browser does is already runnable and
  testable from the command line.
  A native app is one more wrapper around that core, which keeps it thin and testable,
  and lets other shells follow without architectural change.
- **The CLI and the app work together.** A developer who already has the CLI gets an app
  that uses that installation; a user who starts with the app can get the CLI.
- **Plugins never require an app rebuild.** Users and projects add plugins, including
  ones with Python data hooks, to an installed app.

Two further use cases are explored here without a decision: agents controlling a
long-lived server that any viewer (the app or a browser) attaches to in any order, and
the security model such a server needs, from an explicit browsing context to a
Finder-like browser contained by the operating system.

## Summary

- **Architecture:** put a host protocol (ephemeral port, ready line, session token,
  parent-death exit) and a runtime layer (a rootless runtime report, plugin install, and
  an environment builder) into `metab`, each with its parity row and golden.
  Shells then carry platform behavior only.
- **Shell:** a hand-written Swift app hosting `WKWebView` (Option D): under 1.5 MB, no
  entitlements, no third-party runtime dependencies, and the same pattern the sibling
  paraverse app uses. Ship it only after WebKit passes a measurement gate against the
  Chrome-measured bounds; use Electron if it fails, and Tauri if a Windows or Linux app
  becomes near-term.
- **Runtime:** first, the app uses the user’s CLI install.
  Then it adds an app-managed runtime that a bundled uv builds from a hash-pinned
  `pylock.toml`, with an opt-in `metab` launcher for Terminal.
- **Plugins:** live outside the signed bundle, so adding one is a server restart.
  Project-provided plugins need a recorded trust step and their own spec.
- **Distribution:** a notarized DMG and a cask in a personal Homebrew tap; arm64 only,
  macOS 15 or later.
- **Agent-controlled servers (open):** the options run from per-root servers that write
  discoverable state files to one shared per-user server with an explicit browsing
  context; if either is chosen, the app becomes one optional viewer of a server an agent
  may own.
- **Security model (open):** the leaning is a browsing context enforced by the server,
  with client authentication first and a Seatbelt sandbox as the later kernel boundary;
  TCC alone protects too little, and the App Sandbox most likely cannot run a
  uv-installed Python.

What changed since the August brief: the scope is macOS first; Electron’s cost is about
300 MB installed, not the 85–120 MB compressed download; `disable-library-validation` is
needed only for a Python signed inside the bundle; and Electron’s advantage over Tauri
rested on Linux drag-and-drop, which does not apply on macOS.

## Questions to Answer

1. Which shell gives the thinnest usable macOS app?
2. What must `metab` provide so every shell stays a thin, testable wrapper?
3. How do the CLI and the app share an installation?
4. How are plugins added without rebuilding the app?
5. How should the app wrap uv to build its own runtime?
6. Which macOS rules (signing, notarization, Gatekeeper, privacy prompts) shape the
   design?
7. How do users install and update, and what verifies an update?
8. What do shipping apps, and the sibling paraverse app, teach?
9. How could agents control a long-lived server whose views reach every attached viewer,
   with components started in any order?
10. Which security model fits a local file browser that agents control?

## Scope

**In scope:** an arm64 macOS app; the layering between core, CLI, and shells; runtime
provisioning through uv; plugin workflows; distribution and updates; agent-controlled
servers and attach; security models; each option’s consequence for a later Windows or
Linux app.

**Out of scope:** Windows and Linux implementation detail (the August brief and the tbd
Tauri guideline hold the Linux WebKitGTK findings); the Mac App Store; mobile; the full
design of project-provided plugins; the remote/SSH mode, which no option here changes.

## Terms

- **Runtime:** one installation of Metabrowser: a Python environment holding
  metabrowser, its dependencies, and its plugins, plus the cache and config directories
  it owns.
- **Base environment:** a runtime without its plugins: metabrowser and its locked
  dependencies.
- **Install kinds:** a **CLI install** is the user’s own `uv tool install metabrowser`;
  an **app-managed runtime** is one the app builds in Application Support.
- **Python layout:** where an app-managed runtime’s interpreter comes from (see Wrapping
  uv).
- **Host protocol:** what a shell needs from a server it supervises: port, ready line,
  token exchange, health, and shutdown.
- **Browsing context:** the explicit set of folders and files a server is allowed to
  serve, added and removed through `metab`.
- **Boot id:** a random identifier a server picks at each start, which lets clients tell
  a restarted or different server from the one they knew.
- **Acronyms:** PBS is python-build-standalone, Astral’s relocatable CPython builds.
  TCC (Transparency, Consent, and Control) is macOS’s privacy-permission system.
  SSE is server-sent events, CDP the Chrome DevTools Protocol, IPC inter-process
  communication, and CEF the Chromium Embedded Framework.
  The **cool-off** is the [supply-chain policy](../../../SUPPLY-CHAIN-SECURITY.md)’s
  14-day minimum age for third-party releases.

## Findings

### What Metabrowser Requires of a Host

Read from the source at `e1cfca1a` (2026-11-08), about 74k lines of Python and 63k lines
of non-vendored JavaScript, still with no Node build step.

- **One server per root.** `metab ROOT` serves one root on the first free port from
  8411, walking up to 32 ports (`settings.py`, `server_utils.py`). `--port 0` is
  rejected. The `Serving … at http://127.0.0.1:<port>/view/…` line prints before the
  socket listens; the CLI then waits for a 2xx and calls `webbrowser.open`, which
  `--no-open` suppresses (`cli/serve.py`).
- **No session token.** The server validates `Host` against a loopback allowlist,
  returning 421 on mismatch, which defeats DNS rebinding, and requires a same-origin
  proof on `/api`. But `_has_same_origin_proof` in `server.py` accepts a request that
  carries neither `Origin` nor `Sec-Fetch-Site`, so any local process can call every
  route. [SECURITY.md](../../../SECURITY.md) defines Metabrowser as a
  trusted-local-client tool, and the
  [VS Code host draft](../architecture/arch-vscode-extension-host.md) keeps standalone
  behavior unchanged unless a host enables session authentication.
- **`/raw` is a separate surface.** Every `/raw` response is sandboxed with an opaque
  origin, and `/raw` sits outside the origin check (`server.py`), so any authentication
  must work for requests made by sandboxed documents.
- **No host handshake.** There is no single-instance lock, machine-readable ready
  signal, health route, or exit when the parent dies.
  SIGTERM runs uvicorn’s shutdown.
  Git and `gh` children run in their own process groups (`git/process.py`), which the
  server kills on its own interrupt path; a SIGKILL of the server would orphan them.
- **State lives in versioned homes.** The cache and config directories default to
  `~/.cache/metabrowser` and `~/.config/metabrowser` (the XDG locations, overridable by
  flag or environment variable; `home.py`). A runtime that finds a newer cache layout
  than it knows fails with `FutureLayoutFormatError` (`cache/layout.py`). Browser
  preferences live in host-only cookies, which ignore the port, so a shell must keep a
  persistent web data store and an auth cookie needs a per-instance name.
- **Plugins are discovered once, at server import** (`server.py`). Sources are
  built-ins, `metabrowser.plugins` entry points, and folders named by `--plugins-dir` or
  `METABROWSER_PLUGINS_DIRS`. Folder plugins are JavaScript-only, and the served root
  and home directory are deliberately never plugin sources
  ([Plugin Authoring](../../plugins.md)). Python data hooks come only from installed
  packages, which users add with `uv tool install --with`. Invalid plugins, SDK
  mismatches, and data hooks that fail to import are logged and skipped, and the server
  still starts; nothing reports the skipped plugins through a route.
- **The CLI’s probes differ in cost.** `metab --plugins` and `metab --doctor --json` are
  rootless and already report plugin sources and errors.
  `metab --api` requires a root and runs startup work on it.
- **Trust profiles.** `--untrusted` selects the conservative content profile, and
  acquired Git sources always run under it ([command line](../../command-line.md)).
- **External tools depend on `PATH`.** A Finder-launched app gets
  `PATH=/usr/bin:/bin:/usr/sbin:/sbin`. `git` then resolves to the `/usr/bin/git` shim,
  which either shows the Command Line Tools install dialog or runs Apple’s Git, possibly
  below the repository’s 2.43.7 floor; `gh` is not found, so PR features fail.
- **Sizes.** The wheel is 1.9 MB. The 45 runtime packages total about 9.2 MB as arm64
  wheels and 42 MB installed; seven ship compiled extensions (pydantic-core, nh3,
  watchfiles, rpds-py, pyyaml, psutil, markupsafe).
  A uv-installed CPython adds 66–95 MB, depending on the version and whether bytecode
  caches exist.
- **Browser APIs.** The UI uses no Chromium-only API. A shell must handle
  `target=_blank` links, modifier-click “open in new tab”, Back and Forward over
  `pushState`, `window.print()`, `navigator.clipboard.writeText`, and one SSE stream per
  window. The UI binds plain keys and ⌘1–⌘3, leaving ⌘L, ⌘K, ⌘F, ⌘P, and ⌘[ ⌘] free for
  the shell.
- **Engine evidence is Chromium-only.** Every large-content bound was measured in Chrome
  151 and 152 over CDP ([rendering large content](../../large-content-rendering.md)).
  Safari is covered only by manual QA, and Safari Back behavior is unmeasured (bead
  `mb-etqi`).

### macOS Platform Rules

These hold for every shell.
On 2026-11-08 macOS 27 is current, Apple still supports 26 and 15, and 14 has been
unsupported since September 2026.

- **Signing and notarization:** the Apple Developer Program costs $99 a year.
  Notarization requires a Developer ID signature on every executable, the hardened
  runtime, and a secure timestamp; sign nested code inside out, without `--deep`. CI
  uses `notarytool` with an App Store Connect API key and a temporary keychain.
  Staple the app and the DMG; a ZIP cannot be stapled.
  macOS 15 removed the Control-click Gatekeeper bypass, so an unnotarized app needs
  System Settings > Privacy & Security > Open Anyway.
- **Entitlements:** a native shell that runs Python as a separate process needs none;
  Electron needs `allow-jit`. `disable-library-validation` is needed only by a
  hardened-runtime Python signed inside the bundle, because library validation then
  refuses PyPI wheels signed by other teams (reproduced locally).
  Library validation is per process and does not reach an interpreter the shell spawns.
- **Quarantine:** files uv downloads carry `com.apple.provenance` but not
  `com.apple.quarantine`, so Gatekeeper does not block them.
  Never set `LSFileQuarantineEnabled` in the shell’s `Info.plist`: children then
  quarantine everything they write, and macOS kills the resulting binaries
  ([pnpm#11056](https://github.com/pnpm/pnpm/issues/11056)).
- **No App Sandbox, no Mac App Store:** sandboxed children inherit the sandbox, browsing
  arbitrary folders would need per-folder grants, and App Store rules forbid downloaded
  code. Developer ID distribution outside the store is the only fit.
- **Privacy prompts are the largest change for CLI users:** the app is the “responsible
  process” for its child server, so TCC charges the child’s reads to the app.
  Desktop, Documents, Downloads, removable volumes, network volumes, and iCloud Drive
  and other file-provider storage each prompt separately.
  macOS 27 silently denies access to other apps’ containers, and Full Disk Access cannot
  be requested by API. A server started from Terminal uses Terminal’s grants instead, so
  users moving from the CLI see prompts they never saw before.
  The shell declares `NSDesktopFolderUsageDescription`,
  `NSDocumentsFolderUsageDescription`, `NSDownloadsFolderUsageDescription`,
  `NSRemovableVolumesUsageDescription`, `NSNetworkVolumesUsageDescription`,
  `NSFileProviderDomainUsageDescription`, `NSAppDataUsageDescription`, and
  `NSLocalNetworkUsageDescription` (for Git remotes on the local network).
- **Local Network privacy:**
  [TN3179](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy)
  defines the local network as broadcast-capable interfaces, which implies loopback is
  excluded; Apple does not say so directly.
  WKWebView traffic is exempt, and `git` and `gh` to github.com do not prompt.
- **Version and architecture:** Safari 27’s WebKit, which WKWebView provides, ships on
  macOS 15 and later, and about 95% of macOS Homebrew analytics events in the last 30
  days came from macOS 15 or later
  ([Homebrew analytics](https://formulae.brew.sh/api/analytics/os-version/30d.json)).
  macOS 26 is the last release for Intel Macs.
  Target arm64 on macOS 15; Intel users keep the CLI.
- **Homebrew:** [Homebrew 5.0.0](https://brew.sh/2025/11/12/homebrew-5.0.0) deprecated
  `--no-quarantine` and announced that official casks failing Gatekeeper would be
  disabled; they were, from 2026-09-01. Because Homebrew quarantines cask downloads, a
  cask in a personal tap almost certainly needs a notarized app too (inferred, not
  tested). The official cask repository requires 225 stars, 90 forks, or 90 watchers for
  a self-submitted cask, so a personal tap comes first.

### Wrapping uv

Measured on a macOS 26.5 arm64 machine with full Xcode, in an isolated lab, with uv
source read at `3e2f08f8e`. These rules govern every uv call the app or `metab` makes on
an app-managed runtime.

- **Versions:** uv 0.13.5 (2026-10-22) is the newest release past the cool-off; uv
  releases two or three times a week.
  PBS `20261021` is the newest past it.
  Pin CPython 3.14.9, which resolves wheel-only on arm64; 3.15 fails because pyyaml has
  no cp315 wheel yet. uv supports macOS 13 and later.
- **The uv binary:** 27.9 MB on arm64 (14.4 MB compressed), MIT or Apache-2.0, with no
  universal build. Since 0.12.12 the official binaries are Developer ID signed, hardened,
  and notarized (checked with `codesign` on the 0.13.5 binary, identifier
  `sh.astral.uv`). The app re-signs its copy like any nested code.
- **`uv tool install` cannot build an app-managed runtime:** it ignores hashes in
  constraint and requirement files (an install with a bogus hash succeeded) and reads
  the user’s uv configuration.
  Its preview `tool-install-locks` feature reuses a lock uv writes itself; installing
  from a release-supplied lock exists only as draft pull requests
  ([uv#21962](https://github.com/astral-sh/uv/pull/21962)). Use `uv venv` followed by
  `uv pip sync --require-hashes --no-build pylock.toml`, which rejected a wrong hash.
  Without `--no-build`, a hashed `requirements.txt` silently fell back to building a
  source distribution.
- **Isolate every uv call** behind one function:
  - Pass `--no-config --config-file <bundle>/uv.toml`. `--config-file` alone still
    obeyed a `.python-version` in the working directory, and without either flag the
    developer’s own `~/.config/uv` settings leaked into resolution.
  - Spawn with a cleared environment and an allowlist: `UV_*` variables outrank config
    files, and `UV_INDEX_URL` leaked straight through `--config-file`.
  - Point `UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, `UV_PYTHON_BIN_DIR`, `UV_TOOL_DIR`,
    and `UV_TOOL_BIN_DIR` at app-owned directories.
  - Set `UV_MANAGED_PYTHON=1` (without `--managed-python`, uv picked Xcode’s Python
    3.9), pass an explicit `--python 3.14.9`, and pass `--no-bin` to
    `uv python install`, which otherwise writes into `~/.local/bin`.
- **The cool-off applies at release time:** CI locks a small runtime project
  (`metabrowser==X` with `exclude-newer = "14 days"`, first-party packages exempt),
  exports `pylock.toml`, and tests an environment built from that exact file with the
  exact uv binary the app ships.
  The base environment never resolves on the user’s machine.
- **Environment lifecycle:** build each base into `envs/<lock-sha>`, reinstall plugins
  (a base `pip sync` removes them), run a smoke test, swap an `env` symlink atomically,
  and keep the previous environment for rollback.
  `uv pip sync --check` takes 30 ms but missed a deleted file, so the smoke test is the
  real health check. Repair with `uv pip sync --reinstall --offline`, then a rebuild.

Four Python layouts answer where an app-managed runtime’s interpreter comes from:

| Python layout | The bundle carries | First run | Signing consequence |
| --- | --- | --- | --- |
| **uv only** | signed uv, `pylock.toml` | downloads about 36 MB (25 MB Python, 10 MB wheels); 7–9 s on a fast link, about 20–25 s at 20 Mbit/s | none; Python lives in app data, unsigned by us |
| **uv plus Python archive** | the above, plus the 25 MB PBS tarball as a `file://` mirror | Python installs offline in 0.5 s, verified against uv’s compiled-in SHA-256; wheels still download | as above; notarization of a nested archive holding ad-hoc Mach-O files is untested |
| **signed bundled Python** | the above, plus a PBS tree with every Mach-O signed | offline; wheels download or ship prebuilt | the bundled Python needs `disable-library-validation`; a venv built on it broke when the app moved (renames, or App Translocation, where macOS runs a downloaded app from a randomized read-only path), so it must be rebuilt or repointed at launch |
| **user’s uv** | nothing | `uvx metabrowser@X` at each launch | none; but no hash pinning, the user’s config applies, and a Finder-launched app cannot find uv on `PATH` |

“User’s uv” is a developer convenience, distinct from using a CLI install, which runs an
installed `metab` instead of resolving one at each launch.
Frozen packagers (PyInstaller, Nuitka, py2app, Briefcase as the app builder) are a fifth
layout that breaks third-party plugin installs; see Eliminated Options.

Shipping apps surfaced two hazards that the lab machine, which has full Xcode, could not
reproduce:

- **The Command Line Tools prompt:** uv’s managed-Python install calls
  `install_name_tool`, which on a Mac without the Command Line Tools triggers the
  “install developer tools” dialog
  ([uv#14893](https://github.com/astral-sh/uv/issues/14893), open).
  Anki shipped a no-op `install_name_tool` stub on `PATH` to avoid it; uv has an open
  pull request for native Mach-O editing.
- **SIGKILLed managed Python:** on some Macs the system kills uv’s ad-hoc-signed Python
  ([uv#16726](https://github.com/astral-sh/uv/issues/16726), open); a maintainer asked
  whether affected machines are managed or run endpoint security software.
  The signed bundled Python layout is the fallback.

Corporate TLS interception also needs `UV_SYSTEM_CERTS`, and the first import of the
seven native extensions costs about 2 s in total, once, for a macOS security scan.

### The Sibling Paraverse App

[jlevy/paraverse](https://github.com/jlevy/paraverse) already implements the pattern
this brief recommends.
Its `native/` directory is a SwiftPM-only SwiftUI and AppKit app (macOS 14+, no package
dependencies, no Xcode project), and its knowledge-base window is a `WKWebView` pointed
at a loopback Starlette and uvicorn server using plain ES modules and SSE, the same
server shape as Metabrowser.

- **What works well:** one file of about 450 lines holds the whole web-shell part.
  `build-app.sh` runs `swift build -c release`, builds the icon with `iconutil`,
  assembles the bundle from a heredoc `Info.plist`, and signs it, all headless.
  A clean release build took 37–40 s; a minimal SwiftUI, `WKWebView`, and `Process`
  shell built for comparison took about 8 s and was 80 KB (arm64). Server lifecycle is a
  main-actor state machine with injectable probe and process factories, so tests can
  drive it, plus a 0600 log whose tail appears in the failure panel, 250 ms readiness
  polling, a warm server kept across window close (reopen took about 1.6 ms), and
  SIGTERM, a 35 s wait, then SIGKILL of exactly the child it started.
  Same-origin navigation stays in the window; external links open in the default
  browser.
- **What it skipped:** the app runs the checkout’s existing venv, so the bundle must
  stay inside the repository; its README says it is not a self-contained distribution.
  It uses fixed ports and no token, has no notarization, updater, DMG, cask, or CI, and
  signs with a development identity (or ad hoc) mainly so privacy grants survive
  rebuilds.
- **What it learned the hard way:** killing only the Python child orphaned a daemon that
  child had started; a fixed port let the app reuse a server showing the wrong data,
  fixed by an identity check; quit does not wait for the child to finish; and a
  zero-basis `flex: 1` layout collapsed in WKWebView while rendering correctly in other
  engines.

What transfers: the SwiftPM-plus-script build, the WKWebView navigation policy, the
tested lifecycle state machine and its log-tail error UI, a stable signing identity, and
a WebKit test pass. What must differ: runtime discovery and provisioning instead of a
fixed path, ephemeral ports and a token instead of fixed ports and an identity check, a
parent-death exit, a persistent web data store (paraverse uses a non-persistent one),
and everything on the distribution side.

### What Shipping Apps Do

Apps surveyed from their build configurations and launcher source on 2026-11-08 (Ollama
is a non-Python reference):

| App | Shell | Python | Environment | Plugins | Updates | macOS download |
| --- | --- | --- | --- | --- | --- | --- |
| Comfy Desktop 2 | Electron | small bundled PBS plus a downloaded prebuilt env | per-install directory | `uv pip`, with snapshots and rollback | ToDesktop, electron-updater | 196 MB |
| Datasette Desktop (dormant) | Electron | bundled PBS, venv at first run | `~/.datasette-app/venv` | pip | update-electron-app | 133 MB |
| JupyterLab Desktop | Electron | bundled conda-pack env | `~/Library/jupyterlab-desktop` | pip, conda | update-electron-app | 380 MB |
| Open WebUI Desktop | Electron | downloads PBS (SHA-256 checked), then uv | Application Support | pip at runtime | electron-updater | 135 MB |
| Positron | Electron | the user’s interpreters; installs uv with consent | user envs | pip, uv | VS Code style | 881 MB |
| Anki (since 26.05) | Briefcase | built with uv at build time | inside the app | add-on folders, not pip | downloads a DMG | 228 MB |
| Mu (archived) | pup | bundled PBS | versioned venv in Application Support | pip, replayed on upgrade | manual | 119 MB |
| Kolibri | wxPython and WKWebView | PyInstaller | frozen | none | manual | 66–83 MB |
| Spyder 6, napari | conda constructor `.pkg` | conda | `~/Library/<app>` | conda | lock-file updater or new package | 509–522 MB |
| Ollama | Go and WKWebView | none | `~/.ollama` | none | own updater that checks the code signature | 230 MB |

Positron is the closest precedent for using a user-managed install: it discovers the
user’s interpreters and installs uv only with consent.

Four projects changed course:

- **Anki** went from PyOxidizer to a uv first-run launcher (2025) to Briefcase
  ([anki#5019](https://github.com/ankitects/anki/pull/5019), merged 2026-06-17 UTC). Its
  reasons: a Terminal window that looked “virus-like” and is blocked on managed school
  Macs, uv edge cases (the `install_name_tool` prompt, conda on `PATH`, a stray
  `PYTHONHOME`), no offline install, and the process showing as “python”.
  Anki could freeze because its add-ons are folders, not pip packages.
- **ComfyUI** moved from resolving dependencies at first run to downloading prebuilt
  environments, for GPU-scale dependency sets Metabrowser does not have.
- **Spyder** left py2app for conda installers so users could install plugins.
- **Livebook** replaced its Swift macOS shell and C# Windows shell with Tauri
  ([livebook#3112](https://github.com/livebook-dev/livebook/pull/3112), merged
  2026-01-07) and added a Linux build at the same time; the pull request states no
  reason, so a cross-platform motive is inferred.

What recurs:

1. Apps with pip-installable plugins keep a writable environment outside the bundle (Mu,
   Datasette, Open WebUI). Only apps whose plugins are not packages freeze; Orange is
   the exception, installing add-ons into its own bundle.
2. Most filed uv bugs in these launchers came from inherited configuration or
   environment, which the isolation rules above close.
   The Command Line Tools prompt, the SIGKILL, and an interrupted first install (legacy
   ComfyUI) did not.
3. First run is silent, in-app, atomic, and recoverable: no Terminal window, a progress
   view, and a completion marker written only after success.
4. The shell and the environment update separately; an app update triggers an
   environment reconcile.
5. No app relies on the login shell’s `PATH`; JupyterLab and Positron both work around
   it.

Anki’s reversal is the strongest evidence against a uv first-run launcher.
A native shell avoids most of its causes (the Terminal window, the process identity,
inherited uv configuration); offline install and the Command Line Tools prompt need the
direct answers above.

## Proposed Architecture

### Layering: `metab` Is the Product, Shells Are Wrappers

[Views, Models, and Routes](../architecture/arch-views-models-routes.md) already
requires that every route, model, and persisted state have a `metab` equivalent and a
golden transcript, and that only paint and platform behavior be browser-only.
The same rule, applied one level up, makes a shell thin by construction: anything a
shell does that is not platform behavior belongs in `metab`, where it is testable from
the command line.

| Layer | What it holds | How it is tested | Today |
| --- | --- | --- | --- |
| **Core** | routes, models, persisted state, browser state machines | `metab --api` goldens; browserless sessions against the production JS | exists |
| **Host protocol** | the serve mode a shell drives | a reference host in the test suite and a golden session | missing |
| **Runtime** | one installation and the commands that describe and change it | goldens against fixture plugin packages | partial (`--plugins`, `--doctor`) |
| **Shells** | platform behavior only | unit tests with injected process factories; a QA playbook for the exemptions | VS Code host drafted |

Every shell speaks one contract: the macOS app, the drafted
[VS Code host](../architecture/arch-vscode-extension-host.md) (bead `mb-x4y5`), a
browser app window, and any later Windows or Linux shell.
The layering costs nothing at run time, because the page talks to the server directly
over HTTP and SSE and the shell never sits on the request path.

These are the adjustments, each a route or flag with its parity row and golden:

1. **Host mode for serving:** `--port 0`; a JSON ready line (URL, port, PID, package
   version, host-protocol version) printed after the socket listens; and a session token
   that the shell writes as the first line of the child’s stdin rather than the
   environment, which Git and `gh` children would inherit.
   The stdin pipe then stays open as the parent-death signal: EOF means exit.
   The token is exchanged at a one-time URL for an HttpOnly, SameSite=Strict cookie with
   a per-instance name, which gates the page, `/api`, and the event stream.
   `/raw` needs a different gate, such as a per-instance path secret, because requests
   from its sandboxed documents count as cross-site and never carry that cookie; test it
   in both engines. Add `/healthz` and a bounded SIGTERM shutdown that also ends Git and
   `gh` process groups.
   Authentication applies only when a host enables it; hardening the standalone CLI is a
   separate decision under SECURITY.md, though the agent-controlled server use cases
   force it, because an agent-started CLI server that the app attaches to is the
   standalone CLI.
2. **A rootless runtime report:** extend `metab --doctor --json`, which is already
   rootless and already reports plugin sources and errors, with the package and
   host-protocol versions, the Python executable, the environment prefix, the install
   kind, the state homes, skipped plugins with reasons, and the resolved `git` and `gh`
   paths and versions. Share its model with a route so the page can render it.
   `metab --api` is the wrong probe: it needs a root and runs startup work there, which
   could trigger privacy prompts before the user picks a folder.
3. **Plugin install, remove, and list as a CLI mode:** it uses the right uv mechanism
   for the install kind (see Adding Plugins), reads the installed requirement set from
   uv rather than keeping a parallel record, and runs only while that runtime’s servers
   are stopped, or stages into a new environment and swaps.
   Reinstalling a live environment would break deferred imports in running servers.
4. **A runtime builder:** a stdlib-only Python script, in the repository and in the app
   bundle, that turns a uv binary, a `pylock.toml`, and a target directory into a
   verified runtime (create the environment, sync, reinstall plugins, smoke test, swap,
   roll back), reporting progress as JSON lines.
   A clean Mac has no usable Python (`/usr/bin/python3` is a Command Line Tools shim),
   so the shell first runs an isolated `uv python install` and then runs the builder
   with that interpreter.
   The app, CI, and the VS Code host run the same script, so the uv logic is tested once
   in Python. The VS Code draft’s Decision 3, which uses `uv tool install`, would change
   to this builder, since `uv tool install` ignores hashes.
5. **Explicit tool paths:** configuration keys or environment variables for `git` and
   `gh`, a documented `PATH` policy for hosted runs, and a clear missing-tool error.
6. **Privacy-safe I/O:** no reads of a protected folder before the user navigates into
   it, and a structured permission-denied error that the UI turns into a “grant access”
   link.
7. **Settings and plugin pages served by Metabrowser:** the runtime report, settings,
   and the plugin list are Metabrowser pages backed by routes, so every shell shares
   them. Settings that change what Metabrowser does (plugin folders, tool paths) live in
   `metab`’s config file; only shell settings (which runtime, window state) live in the
   app’s preferences.

Two decisions hold for the first steps.
**One server per root:** the shell starts a server per root, which needs no change to
the server, keeps each root’s plugins on their own origin, and avoids the stable-origin
work a browser app window would need; whether a shared, agent-controlled server should
replace it is open (see Use Cases Under Exploration).
**The page never calls a shell API**, so any shell can replace another.

The shell-only exemptions, each with its reason: finding a runtime and the first-run
screen (no `metab` exists yet to ask); windows, menus, the Dock, and file and URL events
(platform behavior); privacy prompts, Gatekeeper, and signing (only a signed build on a
real Mac shows them).
Evidence comes from three places.
The reference host and the runtime goldens run in CI on Linux and macOS. The shell’s
state machine is unit-tested against a fake runtime that speaks the host protocol, the
paraverse pattern. The exemptions get a QA playbook.

### Sharing an Installation Between the CLI and the App

The app talks to a runtime only through `metab`, so it supports both install kinds:

| Install kind | Who builds it | Where | Plugins | Core updates | Fits |
| --- | --- | --- | --- | --- | --- |
| **CLI install** | the user, with the documented `uv tool install metabrowser` | uv’s tool directory, with `metab` on `PATH` | shared by the CLI and the app | the user, with `uv tool upgrade` | developers who already use the CLI |
| **App-managed runtime** | the app’s runtime builder, from the app’s hash-pinned `pylock.toml` | Application Support | the plugin CLI mode, reinstalled on each base change | with each app update | everyone else, including managed and offline Macs |

- **App to CLI:** with a CLI install, the app runs the same `metab` the user does.
  With an app-managed runtime, an opt-in “Install command-line tool” puts a small
  `metab` launcher on `PATH` that runs that runtime with its own state homes.
- **CLI to app:** `metab` hands a request to the installed app as a `metabrowser://` URL
  opened through LaunchServices, carrying the root, path, and flags such as
  `--untrusted` and plugin folders.
  A bare `open -b <bundle-id> ROOT` would drop those flags and could serve an
  `--untrusted` request under the trusted profile.
- **Discovery:** the first-run screen probes the configured path, `metab` resolved once
  through the user’s login shell, `~/.local/bin`, uv’s tool directory, and the Homebrew
  prefixes. It runs the rootless runtime report on each candidate and offers “Use your
  installed Metabrowser” or “Use a copy managed by this app”.
  The served settings page shows the active runtime and offers Switch, Run Doctor, and
  Reveal Logs.

**Delegating to the CLI installer** was the third candidate: the app would run the
documented `uv tool install` for a user who has no CLI. It does not hold up.
The app’s uv is isolated to app-owned directories, so the result would not be an
ordinary CLI install unless the app also installs uv onto `PATH`. The install would
resolve on the user’s machine with no cool-off unless the app passes `--exclude-newer`,
and it would hit uv#14893 and uv#16726 with no signed-Python fallback.
The command-line launcher for an app-managed runtime gives the same result, a working
`metab` in Terminal, without those costs.

**State homes belong to a runtime.** A runtime and every launcher of it (the app, the
command-line launcher) share one cache home and one config home; two runtimes never
share homes. A CLI install keeps the XDG defaults; an app-managed runtime uses homes
under `~/Library`. The reason is version skew: a newer runtime migrates the cache
layout, after which an older one fails with `FutureLayoutFormatError`, and `config.yml`
has only a create-only writer.
The cost is that an app-managed runtime and a separate CLI install do not share
repository mirrors; users who want one shared state use the CLI install kind.

**The host protocol is a versioned boundary.** A CLI install updates independently of
the app, which makes it the named consumer that
[Compatibility and Legacy Code](../../development.md#compatibility-and-legacy-code)
requires. Its answer for such a boundary is VERSION + FAIL FAST: the app accepts exactly
one host-protocol version, and on a mismatch it says so and offers `uv tool upgrade` or
the app-managed runtime.
The app consumes only the ready line, `/healthz`, and the runtime report; the page and
`/api` come from the same runtime, so “Server APIs: DO NOT MAINTAIN” still holds.
Record this as a new row in that section’s Standing Compatibility Answers table.

### Adding Plugins Without Rebuilding the App

The signed bundle holds only the shell, uv, the lock, and an optional Python archive.
Every plugin lives in a runtime’s environment, a plugin folder, or a project, so no
plugin change touches the bundle.

| Source | Contents | How it is added | Survives core updates | Takes effect after |
| --- | --- | --- | --- | --- |
| **Package plugin** (PyPI, a Git URL, or a local path) | JavaScript and Python data hooks | the plugin CLI mode, from Terminal or the plugin page | yes: uv’s tool receipt for a CLI install; reinstalled by the builder for an app-managed runtime | a server restart |
| **Plugin folder** | JavaScript only | `--plugins-dir`, `METABROWSER_PLUGINS_DIRS`, or a folder list in `metab`’s config | yes | a server restart |
| **Project plugin** (declared by a served repository) | JavaScript first; Python deferred | proposed: declared in the repository and enabled by a recorded trust step | trust is recorded per project | a server restart |

- **Install mechanics differ by install kind, and `metab` hides that.** For a CLI
  install the plugin mode re-runs
  `uv tool install metabrowser==<current> --with <every installed plugin>`, read from
  uv’s receipt, so `uv tool upgrade` keeps the plugins and plugins the user added with
  `--with` are not lost.
  For an app-managed runtime it runs `uv pip install -c base-constraints.txt <plugin>`
  with the uv path the app passes in.
  A plugin that needs a different version of a base package fails cleanly.

- **Plugins resolve on the user’s machine.** The hash-pinned guarantee covers the base
  environment only. An app-managed runtime applies the cool-off to plugins through
  `exclude-newer = "14 days"` in its bundled `uv.toml`; a CLI install follows the user’s
  own uv configuration.
  Git and local-path plugins are trusted by the operator’s choice.

- **A restart is enough.** Discovery runs at server import, so adding a plugin means
  restarting that runtime’s servers and reloading their windows, which a shell does in
  seconds. Hot reloading inside a running server is deliberately deferred in the code and
  is not needed for the app; agent-registered views may change that (see Use Cases Under
  Exploration).

- **Incompatible plugins are already skipped.** A core update can leave a plugin on an
  older `PLUGIN_SDK_VERSION`; serving already skips it and starts.
  The runtime report should list such plugins with the reason, so the user sees why one
  vanished.

- **Project plugins are the new workflow, and they cross a security boundary.** The case
  to support is a repository that ships its own plugin, such as a viewer for its own
  database format, that should work when the repository is opened.
  The served root is never a plugin source today, because browsing data must not run its
  JavaScript. A recorded trust step, in the style of VS Code’s Workspace Trust or
  direnv’s `direnv allow`, keeps that boundary:
  - The repository declares its plugins in a file; Metabrowser reports untrusted project
    plugins for that root, and nothing loads until the operator trusts them through
    `metab` or the app.
  - Trust is recorded in `metab`’s config, keyed by the root and a hash of both the
    declaration and the plugin trees it names, so a `git pull` that changes a plugin’s
    code asks again.
  - JavaScript-only project plugins load like a plugin folder for that root.
    Python project plugins would load for every root and, with a CLI install, for every
    CLI use, with every privacy grant the app holds; defer them or give them a per-root
    overlay environment.
  - Never for acquired Git sources or under `--untrusted`.
  - One server per root keeps a trusted plugin’s JavaScript off other roots’ `/api`; a
    future multi-root origin would remove that isolation.

  This changes the plugin trust model and needs its own spec.

## Use Cases Under Exploration: Agent-Controlled Servers

These use cases are under evaluation, not decided.
This section maps what they need, what the code does today, and the options with their
trade-offs.

### The Use Cases

1. **An agent owns serving.** A user installs the Metabrowser skill; the agent starts a
   server, adds folders and views to it, and opens the result in the user’s browser.
   If the user says they use the native app, the app is a convenient window onto that
   same server, which any browser could also open.
2. **Start in any order.** A server started from the CLI and open in a browser shows the
   same content when the app starts later; an app started first exposes its server to
   the CLI and agents.
3. **A long-lived server.** It is managed externally or restarted and reloaded at any
   time, and views an agent registers appear in every connected window, in the app or a
   browser.
4. **A settable app.** The app can start a server, attach to a running one, or show the
   command an agent should run.
5. **An explicit browsing context.** The server serves only folders and files that the
   user or an agent explicitly added through `metab` commands.

### What the Code Does Today

Read from the source at `e1cfca1a`:

- **No discovery and no identity.** There is no state, pid, or lock file, no list of
  running servers, and no identity or health route.
  `metab --api` runs in-process; no client mode targets a running server.
  An agent changes an open page today mainly by changing files, which the watcher
  pushes, or by calling `POST /api/source/refresh` or `/api/source/pin` directly.
- **Reconnects keep stale state.** The page’s event stream reconnects with backoff and
  receives a fresh snapshot, but nothing replays missed events, and the page keeps its
  old shell, settings, and plugin assets.
  The build tag inlined in the page feeds ETags only and is never compared, so the page
  never reloads after a restart.
  A restart on a different port leaves the page retrying a dead origin.
- **The port walk misroutes tabs.** Because every server walks up from 8411, a server
  for a different root can take a port that open tabs still point at, and they silently
  reattach to the wrong root.
  The source-pin guard is an existing pattern for checking identity and reloading once.
- **The registry is fixed at import.** Plugin discovery, kind rules, and data-hook
  routes are built once.
  The browser SDK can add plugins at runtime but cannot replace a loaded one (loads are
  memoized by name and module URLs are unversioned), and `/api/file` ETags are not
  scoped to a registry revision.
- **One root per process.** The root is a module global used by about 15 modules, with
  one inventory and one subject per process, and URLs carry no root segment.
  `metab file.md` serves the file’s whole parent folder.
- **No authority boundary.** Requests without `Origin` or `Sec-Fetch-Site` pass.
  The `--allow-edits` mutations capability gates no route yet, while
  `POST /api/kpress/export` already writes inside the root, gated only by the folder
  source’s own mutation flag, which every folder has.
- **The skill** starts one background server per path with `--no-open`, reports its URL,
  and reads data with `--api` and `--show`.

### How Other Tools Do It

| Tool | Discovery | Authentication | Attach behavior | Live changes |
| --- | --- | --- | --- | --- |
| Jupyter Server | `jpserver-<pid>.json` in a 0700 runtime directory (URL, port, token, root, pid, version); readers drop dead pids; `jupyter server list --json` | a random token per boot, exchanged once for a cookie whose secret persists across restarts; Host-header check | JupyterLab Desktop starts its own server and can connect to listed external ones | one root per server; extensions need a restart |
| LM Studio | `http-server.json` (port, pid), then a greeting probe | a CLI passkey file | one shared service; the CLI launches the app or daemon | `lms load` changes the live service, restored on launch |
| Ollama | fixed port 11434, probed with `HEAD /` | none on the API | the app replaces a user-started server; the CLI launches the app when the port is down | none found (not exhaustive) |
| Syncthing | API key and address in `config.xml` | `X-API-Key` header | the macOS wrapper always starts its own daemon | folders added over REST and saved; a config event patches the open GUI |
| VS Code | a per-user socket claimed by binding; refusal means stale | socket permissions; an inherited variable for the integrated terminal | a second instance forwards its arguments and exits | `code --add` adds folders to the open window |
| Storybook and Vite | fixed port | none | none | an index-invalidated event makes clients refetch; code changes and restarts force a reload |
| MCP in GUI apps | Figma’s local MCP endpoint; JetBrains’ built-in server with copyable client config | the MCP specification requires Origin validation and recommends authentication; Figma’s page names none | agents connect to the running app | not applicable |

Key sources:
[Jupyter Server’s runtime files](https://github.com/jupyter-server/jupyter_server/blob/e39ebd56b3ed2b201aa615448ec6adbeed8fa99c/jupyter_server/serverapp.py#L3289-L3324),
[JupyterLab Desktop’s server handling](https://github.com/jupyterlab/jupyterlab-desktop/blob/0d7e537b04e49c80ed61911d895273eee9af0f44/src/main/server.ts#L229),
[LM Studio’s `lms` client](https://github.com/lmstudio-ai/lms/blob/43d4b2680e3cf679ad19753fcc7af0cb0e4a12a2/src/localAPIServer.ts),
[Syncthing’s REST API](https://docs.syncthing.net/dev/rest.html),
[VS Code multi-root workspaces](https://code.visualstudio.com/docs/editing/workspaces/multi-root-workspaces),
[Figma’s local MCP server](https://developers.figma.com/docs/figma-mcp-server/local-server-installation/),
and [JetBrains’ MCP server](https://www.jetbrains.com/help/idea/mcp-server.html).

### Options

The server options are lettered P, P+, S, and F to keep them apart from the shell
options A–F.

| Option | What it is | For | Against |
| --- | --- | --- | --- |
| **P: per-root servers the app starts** | the current plan | smallest change; privacy prompts always name the app | fails use cases 1–3: an agent’s server and the app’s are different processes, and nothing is shared or persisted |
| **P+: per-root servers plus state files** | each server writes an owner-only state file (URL, pid, root, boot id); `metab ROOT` reuses a live server for that root; the app lists and attaches to running servers; pages reload once when the boot id changes; a fixed port fails instead of walking | covers start-in-any-order and restart-to-add-a-view for one root; keeps per-root origin isolation; little core change | many ports and processes; views appear only after a restart; no single browsing context |
| **S: one shared per-user server with an explicit browsing context** | a discovery file (`~/Library/Application Support/Metabrowser/run/server.json`, 0600, with pid, URL, version, boot id); an owner-only Unix socket through which the CLI and the app get the token; an unauthenticated identity route checked against the boot id; a lock that serializes find-or-start; a persisted list of added folders and files edited by `metab add`, `metab remove`, and `metab roots` through routes | serves every use case; a stable address for a browser app window; the agent owns the lifecycle and the app is one viewer | the largest refactor (multi-root URLs, per-root inventories and event buses, file-only entries); a new lifecycle to manage (stop, upgrade, version skew between CLI and server); `metab ROOT` changes meaning; one origin shares plugin JavaScript across roots |
| **F: a fixed port only** | discovery by probing a known port | the simplest discovery | the token still needs a file or socket; another program can squat or answer the port; contradicts the port walk; better as a preferred port combined with S’s discovery file |

Under Option S, who starts the shared server decides who gets the privacy prompts:

- **S1: the CLI starts it detached.** It works without the app, but prompts and grants
  name whatever launched the agent (a terminal, an editor, or an agent app), and folders
  granted through the app’s Open panel probably do not apply (untested).
  An agent that is itself sandboxed passes its sandbox to the server it starts, which
  then cannot apply its own profile, and Anthropic’s sandbox runtime blocks local
  listening by default.
- **S2: the CLI asks the app to start it,** as LM Studio and Ollama do.
  Prompts and grants attach to the app, but it needs the app installed and falls back to
  S1 without it. A preference such as “start servers with the app, the CLI, or
  automatically” could choose.
- **S3: a login item** (`SMAppService` LaunchAgent, macOS 13 and later).
  It is always on and expected to be attributed to the app (untested), at the cost of a
  Login Items approval, a Mach-O launcher (a Python script breaks TCC attribution), and
  less freedom for agents to restart it with new flags.
  The always-on LaunchAgent rejected under Eliminated Options becomes viable only with
  its preconditions met: the token first, and a check that folder access is not silently
  denied.

Two mechanisms can make a newly registered view appear in open windows:

- **Restart and reload.** The server restarts on a stable address; pages see a new boot
  id on reconnect and reload once.
  It needs no registry changes, costs a server start (imports measured at 0.77–0.93 s
  warm, plus an inventory rewalk), and works for Python data hooks, which can only load
  at startup. The cookie secret must persist across restarts, or every reload signs the
  browser out (Jupyter persists it; Livebook does not).
- **A registry revision event.** A `registry-changed` event with a revision tells pages
  to refetch the view list, as Storybook does.
  It needs a mutable registry, ETags scoped to the revision, and dynamic routes, and it
  is tractable only for views defined as data or JavaScript; replacing already-loaded
  code still needs a reload.

Pieces common to every shared-server option:

- **The app’s startup setting:** attach to a running server, start one, or show the
  command for an agent, modeled on JupyterLab Desktop’s connect dialog and JetBrains’
  copyable MCP configuration.
- **Where to open:** `metab` opens in the browser or the app according to a stored
  preference that the CLI and agents honor, passing the URL to the app through its URL
  scheme. Compared with passing a root and flags for the app to spawn a server, this
  needs no flag translation, but the app must verify that the URL names a loopback
  Metabrowser server it trusts.
- **Browsers get a one-time URL** that exchanges the token for a cookie; the CLI and the
  app get the token over the owner-only socket, because a sandboxed agent can often read
  any file in the home folder.
  Tokens stay out of argv and logs; `webbrowser.open` and an agent reporting a tokenized
  URL would leak it, which Jupyter avoids with a redirect file.
- **An optional `metab` MCP adapter** over the same routes would help agents without a
  shell, at the cost of a second surface to keep in parity.

### Questions That Decide It

- Is one browsing context per user worth a multi-root server, or do per-root servers
  with state files (P+) cover the agent workflow well enough?
- Which security model applies (see Security Models)?
  An explicit browsing context is a natural fit for a shared server, and per-root
  servers keep per-origin isolation.
- Who should be charged for privacy prompts, the app or the agent’s host process, and
  does a folder granted in the app’s Open panel cover a child server?
  Both are untested.
- Must views an agent registers be live without a reload, or is reload-on-restart
  enough?

Every option keeps the layering above: discovery, attach, the browsing context, and view
registration are `metab` routes and commands with parity rows and goldens, and the app
stays a viewer that adds only platform behavior.

## Security Models

A long-lived server that agents control and several clients attach to raises the
question of what Metabrowser may read and who may ask it to.
Two framings compete: a server that serves only an explicit browsing context, and a true
local file browser, like Finder, that relies on the operating system or another sandbox
for containment. They are evaluated here as candidates, not decisions.

### Threats

- **Other local processes and users:** today any of them can call every route, because a
  request without `Origin` or `Sec-Fetch-Site` passes.
- **Web pages in the user’s browser:** DNS rebinding is blocked by the Host check;
  Chrome now asks before a public site reaches loopback (its Local Network Access
  prompt), and Safari has announced nothing comparable.
- **Hostile content in browsed files** that exploits a renderer or the server.
- **A confused or malicious agent** that adds too much, or a sandboxed agent or app that
  uses the server to read what its own sandbox forbids.
- **Untrusted plugin or view code**, which runs same-origin with the API.
- **Probing outside the served set:** `/raw` sits outside the origin check, so its
  responses can reveal whether a path exists; a browsing context bounds what such a
  probe can reach.

### Candidate Models

| Model | Protects against | User cost | Code cost | macOS fit |
| --- | --- | --- | --- | --- |
| **Server-enforced browsing context** (only added folders and files) | over-broad clients and agents, containment bugs, probing outside the context | folders must be added first; adding takes effect at once; the app’s Open panel avoids prompts for the app (untested for its server) | moderate: a context registry replaces the global root, files open by descriptor, routes are scoped | good |
| **True local browser, TCC only** | only what TCC protects: Desktop, Documents, Downloads, iCloud and other file providers, removable and network volumes, other apps’ data | best, Finder-like | smallest | not a secrets boundary: `~/.ssh`, `~/.aws`, dotfiles, and browser profiles are unprotected ([Eclectic Light, macOS 26.4](https://eclecticlight.co/2026/04/15/privacy-which-folders-are-protected-in-tahoe/)) |
| **Seatbelt worker** (a `sandbox-exec` profile generated from the context) | a compromised server process, path bugs, symlink tricks | a server restart whenever the context grows (time unmeasured) | moderate to high: a supervisor, a profile generator, a helper for Git’s network access, a Linux counterpart | Seatbelt is relied on through the deprecated `sandbox-exec` by Anthropic’s sandbox runtime, OpenAI Codex, Bazel, and SwiftPM, and directly by Chromium; a uv-installed CPython ran under a deny-by-default read allowlist in a probe |
| **App Sandbox with security-scoped bookmarks** | a compromised server | an Open panel per folder; only the app can start the server | high | poor: children inherit only static rights, not Powerbox grants, and Apple DTS says executables a sandboxed app creates are always quarantined, so a Python the sandboxed app downloads most likely cannot run (inferred; unlike the unsandboxed case under Quarantine above) |
| **Separate user, virtual machine, or container** | nearly everything | heavy | high | Apple’s `container` needs macOS 26; worth it only for hostile acquired content |

Two layers apply under every model:

- **Client authentication:** a token per server start, an owner-only Unix socket for the
  CLI, agents, and the app (checked with `getpeereid`), and a one-time URL that gives
  browsers a cookie, with `/raw` behind a secret path prefix.
  Socket ownership and `getpeereid` authenticate a user, not an individual application.
  Another process running as that user can obtain the token if it can connect to the
  socket; this alone does not prevent relaying the starter’s privacy grants to it.
  A sandboxed client is excluded only if its sandbox denies socket access or a separate
  authorization step refuses it.
  Browsers cannot use a Unix socket, so loopback TCP stays for them.
- **Plugin and view isolation:** at minimum declarative agent-registered views and a
  content security policy that keeps data on the machine (`connect-src 'self'`); later,
  plugin views in opaque-origin iframes with a message-passing SDK (a
  `PLUGIN_SDK_VERSION` break) and Python hooks out of process.

### What the Probes and Code Show

- **Containment checks a path, then reopens it by name.** `_safe_path` and the content
  source resolve and check a path, and `FileResponse` opens the same name later, so a
  writer inside a served folder could swap in a symlink in between.
  That matters only for an adversary who can write inside the folder but cannot read the
  target directly, such as a sandboxed agent.
- **Hidden names are hidden in the tree but not refused** by the resolvers (inferred
  from the code, not exercised against a running server).
- **Python path checks keep the spelling given:** `realpath` preserves case and the
  `/System/Volumes/Data` firmlink prefix, which fails closed under an allowlist and open
  under a deny list; with today’s single root this is harmless.
  Seatbelt normalizes case, firmlink, `/tmp`, and symlink spellings, but an existing
  hard link bypasses its path rules (a sandboxed process cannot create one).
- **macOS can open files strictly beneath a folder:** `O_RESOLVE_BENEATH` refuses `..`,
  absolute paths, and escaping symlinks (it appears in a 2025 XNU release, inferred to
  be macOS 15.4; Python lacks the constant), `O_UNIQUE` refuses hard-linked files on
  macOS 26, and `F_GETPATH` returns the canonical path of an opened file on any version.
- **A Seatbelt profile cannot change after launch,** and a passed directory descriptor
  does not grant its subtree, so a growing context means restarting the worker.
  The alternatives are brokering file descriptors from an unsandboxed helper (heavy) or
  WebKit’s private sandbox-extension interface (not public API).
- **A server must exclude its own secrets.** Jupyter Server leaked its token through its
  own API when it served the home folder
  ([GHSA-q874-g24w-4q9g](https://github.com/advisories/GHSA-q874-g24w-4q9g)).
- **Codex guards its own daemon from sandboxed commands** by denying them its socket
  directory, and Anthropic’s sandbox runtime blocks Unix sockets by default.

### Leaning and Trade-Offs

The two framings overlap more than they compete.
“Browse anything” can be a broad entry the user deliberately adds to the browsing
context, and a Seatbelt worker is what later turns the context into a kernel-enforced
boundary. The fairest case for the TCC-only model is that it matches Finder, costs the
least code, and adds little against an unsandboxed agent that can already read
everything. Its weakness is that a server exploit by hostile content would expose every
secret in the home folder; client authentication, which applies under every model,
blocks unauthenticated web pages, but not a compromised server or a same-user client
that can obtain the token.

If a long-lived, multi-client server goes ahead, these would come first:

1. Client authentication as above, removing the “no headers means trusted” branch while
   keeping the Host and origin checks.
2. One owner that starts the server, so its privacy identity does not depend on who
   asked: the app’s login item (S3) or a documented `metab` daemon whose attribution is
   documented as the terminal’s (S1). This narrows S1–S3 and is in tension with starting
   in any order, so it is part of the same decision.
3. The browsing context enforced by the server: open files by descriptor beneath each
   entry, verify opened paths with `F_GETPATH`, refuse hidden names by default, exclude
   the server’s own state, and put every route, data hook, Git child, and watcher behind
   the context.
4. No broad entries (`/`, `~`, `~/Library`, credential folders) added by an agent
   without a user step.
5. Declarative agent-registered views and a strict content security policy.

Later, in order: a Seatbelt worker on macOS (Landlock or bubblewrap on Linux), scoped
and expiring agent tokens with an audit log, iframe-isolated plugin views and
out-of-process Python hooks, per-context ports, and a virtual-machine mode for hostile
sources. The App Sandbox for the server, and TCC as the only gate, are the two models
this research does not favor.

Open questions: whether a folder picked in the app’s Open panel reaches a child or
launchd-started server; how TCC attributes an `SMAppService` server versus one started
from Terminal; how long a Seatbelt worker restart takes, including the event-stream
reconnect, on which the restart model stands or falls; whether a narrowed production
profile still runs uvicorn, FSEvents, Git, and `gh`; whether clipboard writes work on
the loopback origin in WebKit (the secure context itself was verified in the probe); how
to treat hard links and mount points; whether agent tokens should bind to the client’s
code signature; and whether these results hold on macOS 27 (the probes ran on 26.5).

## Comparison Matrix

Sizes are arm64 and, for D and E, estimates.
“Shell plus uv” assumes the uv-only Python layout; the Python archive adds 25 MB. Every
shell can use a CLI install, because each talks only to `metab`.

| Criterion | A: No shell | B: Browser app window | C: pywebview | D: Swift shell | E: Tauri 2 | F: Electron |
| --- | --- | --- | --- | --- | --- | --- |
| Who can install | uv users | uv users with Chrome or Edge | uv users | anyone | anyone | anyone |
| Download, shell plus uv | none | none | none (in the CLI install) | about 16 MB | about 15–20 MB | about 135 MB |
| Installed shell | none | none | about 33 MB of PyObjC in the uv env | under 1.5 MB | under 10 MB | about 300 MB |
| Shell code | none | tens of lines in `metab` | about 100 lines of Python (sketch) | 150 lines minimal (built); 1,200–1,500 full | 150–250 lines of Rust plus 40 of config, minimal; full wiring as D, not estimated | about 90 lines of JS, minimal; full needs less than D |
| New toolchain | none | none | PyObjC | Swift; no third-party packages until Sparkle | Rust; about 278 crates | none new; about 288 npm build packages |
| Engine | user’s browser | Chrome | WebKit | WebKit | WebKit | Chromium 156 |
| Open With, folder drop, URL scheme | no | no | no | yes | yes | yes |
| Find in page | browser | browser | no | custom find bar | custom find bar | built in |
| Update integrity | uv, no hash check | uv, no hash check | uv, no hash check | cask, then Sparkle EdDSA | minisign key compiled in | Squirrel.Mac code-signature check |
| Entitlements | none | none | none | none (signed bundled Python adds `disable-library-validation`) | as D | `allow-jit` |
| Memory, one window | a browser tab | a Chrome app | WebKit | WebKit: about 78 MB in one probe sample | WebKit | Chromium: 150–400 MB, estimated |
| Later Windows or Linux | works | works | partial | a second shell | same shell | same shell |
| Main risk | no app identity | needs a stable origin | one maintainer; missing APIs | macOS only; WebKit only | Rust and cargo supply chain; WebKit only | size; Chromium patch cadence |

## Options Considered

### Option A: No Shell (the CLI and the User’s Browser)

**Description:** The status quo.

**Pros:**

- Install and update are solved by uv.
- No signing, notarization, or new CI.
- The remote/SSH mode depends on exactly this shape.

**Cons:**

- Requires uv, which rules out users without it.
- Dependencies resolve on the user’s machine, with the cool-off only if their uv
  configuration sets it and no hash checks.
- No Dock identity, file associations, or URL scheme.

### Option B: Browser-Provided App Window (`metab app`)

**Description:** A web app manifest plus a `metab app` command that opens Metabrowser as
an installed Chrome or Edge web app, falling back to a Chromium `--app` window and then
the default browser.
Once a native app exists, the same command hands the request to it.

**Pros:**

- Chrome no longer requires a service worker for menu install
  ([install criteria](https://developer.chrome.com/blog/update-install-criteria)), and
  `127.0.0.1` qualifies on any port.
  Chrome writes an app shim to `~/Applications/Chrome Apps.localized/` with its own Dock
  icon, ⌘-Tab entry, and a window without browser chrome.
- A few dozen lines in `metab`; no signing.
- A Finder Quick Action (“Open in Metabrowser”) can call `metab` with no shell app.

**Cons:**

- A web app’s identity is its origin, port included, so ports 8411 and 8412 are two
  different apps. This needs one stable origin serving several roots, which Metabrowser
  does not have and which would remove the per-root plugin isolation.
- When the server is down, the app shows a connection error; nothing can start it.
- Chromium `--app` windows show Chrome’s identity, and Safari’s “Add to Dock” on a
  loopback origin is unverified.
- No folder drop, Open With, or `metabrowser://` without an extra applet.

**Verdict:** a cheap complement once a stable origin exists, not the native app.

### Option C: pywebview Window from the CLI Install

**Description:** `uv tool install 'metabrowser[app]'` adds
[pywebview](https://github.com/r0x0r/pywebview) 6.2.1 (WKWebView through PyObjC), and
`metab app` runs the server as a child with a token and opens a native window.

**Pros:**

- All Python; no new language.
- The same WebKit engine as Options D and E.
- File drops arrive with full paths; downloads, multiple windows, and custom menus work.

**Cons:**

- No find in page, no URL-scheme or file-open handlers (an issue open since 2020), and
  no status item. On macOS 26, window buttons can become unclickable
  ([pywebview#1866](https://github.com/r0x0r/pywebview/issues/1866)).
- Essentially one maintainer, and a dependency, `proxy_tools`, exists only as a 2014
  source distribution that every install builds.
- The process shows as “python” unless a locally generated launcher bundle symlinks into
  the uv environment. A distributable signed app needs a Mach-O inside the bundle as the
  GUI process, which means a signed bundled Python running PyObjC: more machinery than
  Option D for less capability.
- A GUI dependency joins the CLI install.

**Verdict:** a reasonable developer window for existing CLI users; not the distributable
app.

### Option D: Hand-Written Swift Shell (Recommended)

**Description:** An AppKit app hosting `WKWebView`, built with SwiftPM and a
bundle-assembly script, as paraverse does.
It finds or builds a runtime, spawns one host-mode `metab` server per root with
`posix_spawn` in its own process group, writes the token to the child’s stdin, reads the
ready line, and loads `http://127.0.0.1:<port>` with a persistent data store.
Everything else, including settings and plugin pages, comes from `metab`.

**Pros:**

- **Thinnest native app:** a 150-line AppKit and `WKWebView` probe built during this
  research was 245 KB as a universal binary.
  A full shell should stay under 1.5 MB, plus about 3 MB if Sparkle is added.
  On a trivial page the probe’s processes used about 78 MB against about 362 MB for
  headless Chrome, in one rough sample.
- **No entitlements and no third-party runtime dependencies,** which keeps signing,
  notarization, and the supply-chain policy simple.
- **Every native affordance is available directly:** folder drop on the Dock icon, Open
  With, a `metabrowser://` scheme, a Quick Action, a dock menu, window restoration, and
  absolute file paths from drops, which a browser does not provide.
- **Verified on loopback in the probe:** SSE, cookies, local storage, and a secure
  context, with no App Transport Security exception (set `NSAllowsLocalNetworking`
  anyway). Clipboard writes should therefore work; that is inferred, not tested.
- **Builds headless in seconds** on a machine with Xcode (a Command Line Tools–only
  build is untested), and paraverse already uses this build and lifecycle.
- **Updates can start simple:** a Homebrew cask plus an in-app “update available”
  notice, adding [Sparkle](https://sparkle-project.org/) 2 (EdDSA-signed appcasts on
  GitHub Releases, with no XPC services needed outside the sandbox) when shell updates
  become routine.

**Cons:**

- **macOS only.** A Windows or Linux app later means a second shell, as Livebook found;
  the shared host protocol, runtime commands, and builder bound that cost.
- **WebKit becomes the only engine,** and Metabrowser’s bounds were measured in Chrome.
- The shell must implement what a browser provides: downloads (`WKDownload`),
  `target=_blank` (`createWebViewWith`), the find bar (`WKWebView` is an
  `NSTextFinderClient`, but the bar container is yours to build), Web Inspector access
  (`isInspectable`), and probably printing (`window.print()` is unverified in the
  probe).
- Swift is a new language in the repository; Swift 6 strict concurrency caused friction
  in background I/O callbacks, fixed with `nonisolated` in the probe.
- It needs a macOS CI job; Linux `make verify` can neither build nor test it.
- Sparkle had five security advisories in 2026, all fixed by 2.9.6
  ([advisories](https://github.com/sparkle-project/Sparkle/security)); pin 2.10.0 or
  later.
- Do not use the macOS 26 SwiftUI `WebView` and `WebPage` API: it lacks downloads, page
  zoom, and a `createWebViewWith` equivalent, and hides its `WKWebView`.

### Option E: Tauri 2 Shell (Runner-Up)

**Description:** A Tauri 2.12.5 app whose window loads the loopback URL with
`WebviewUrl::External`, with uv as a signed `externalBin` spawned from Rust in its own
process group. No frontend build is needed.

**Pros:**

- **Zero capability files:** Tauri treats the loopback page as a remote origin, so every
  IPC call is rejected and the page has no shell API.
- **The strongest built-in updater:** minisign verification against a public key
  compiled into the app, `requireSignedVersion` to block downgrades, and an atomic swap
  with rollback on macOS (updater 2.12–2.14).
- About 15–20 MB with uv; a two-architecture DMG of a thin Tauri wrapper is 8–9.4 MB.
- One shell for Windows and Linux later.

**Cons:**

- **Rust and cargo** become a third package ecosystem: about 278 crate versions, and a
  fresh resolve pulled 19 crates younger than 14 days.
  Cargo’s `registry.global-min-publish-age` would enforce the cool-off and is reported
  for Rust 1.100
  ([Cargo configuration](https://doc.rust-lang.org/nightly/cargo/reference/config.html);
  release date unconfirmed).
- **Security floor:** 2.11.6, for
  [GHSA-w28w-mhc8-qvjv](https://github.com/tauri-apps/tauri/security/advisories/GHSA-w28w-mhc8-qvjv),
  where one webview could read another’s IPC payloads.
- **The same WebKit engine and the same wiring as Option D:** `target=_blank`,
  downloads, Reload, Back and Forward, and Find all fail silently until the shell
  implements them. Drag-and-drop is either-or: Tauri’s handler swallows HTML5 drops but
  gives Rust real paths.
  Release-build devtools need a feature that uses private APIs.
- The bundler signs `externalBin` but not Mach-O files under resources, and it applies
  one entitlements file to every binary.
  The shell plugin auto-kills only children spawned from JavaScript, not from Rust,
  contrary to the tbd Tauri guideline.
- Tauri 3.0 is at alpha 6. Its headline change is an optional CEF runtime, 128.7 MiB
  (135 MB) compressed on arm64, which would make that option Electron-sized.

**Verdict:** choose Tauri over Swift if a Windows or Linux app is on the near-term
roadmap, or if a verified updater from day one outweighs adding Rust.

### Option F: Electron Shell (Fallback If WebKit Fails)

**Description:** One `main.js` of about 90 lines loaded directly by Electron 45, with no
Vite, preload, renderer build, or IPC, type-checked with `// @ts-check` under the
existing TypeScript gate.
The bundled uv lives in `Contents/Helpers`.

**Pros:**

- **Chromium parity** with the engine every performance bound was measured in, plus
  DevTools in the product.
- No new ecosystem: the repository already has npm, Biome, and TypeScript.
- Mature macOS integration: single-instance lock, `open-file` and `open-url`, protocols,
  a dock menu, and experimental native window-state persistence (Electron 44).
- Squirrel.Mac validates each update against the running app’s designated requirement,
  and the built-in updater in Electron 44 and 45 also checks a SHA-256 and size from the
  feed.

**Cons:**

- **Size:** the arm64 runtime is a 121 MB download and about 300 MB installed (about
  1.6x for universal), and one window uses an estimated 150–400 MB, duplicated against
  the user’s own browser.
- **Patch cadence:** supported majors are 43, 44, and 45 (42 reached end of life on
  2026-10-20); Chrome now ships a milestone every two weeks, and 15 Electron security
  advisories have appeared since 2026-08-16
  ([advisories](https://github.com/electron/electron/security/advisories)). Releases
  routinely need the cool-off’s security exception.
- electron-builder 26’s default macOS entitlements grant `allow-jit`,
  `allow-unsigned-executable-memory`, and `disable-library-validation`; always supply a
  narrower file. Signed update manifests exist only in electron-updater 7 alphas.

**Verdict:** the right shell only if WebKit fails the measurement gate, or if Chromium
parity with the measurement harness turns out to matter more than about 300 MB.

### Eliminated Options

- **Electrobun (2.0.6, 2026-11-04):** still eliminated for public distribution.
  The updater now checks an optional SHA-256, but the digest comes from the same
  unauthenticated host as the payload, so it catches corruption, not tampering.
  There is still no signature, and the updater strips quarantine without checking the
  new app’s code signature.
  Every commit since 2026-08-16 is by one maintainer.
  It also ships the Bun runtime (about 40 MB zipped) just to start uv and show one
  WKWebView, installs through a self-extracting wrapper, and cannot register for
  existing document types.
- **Wails v3 (Go):** v3.0.0 reached general availability on 2026-10-26, and v3.1.0
  followed on 2026-11-01, both inside the cool-off.
  At the commit read, its macOS code had no new-window, navigation-policy, or download
  handling, so `target=_blank` links most likely do nothing (open upstream as
  [wails#5043](https://github.com/wailsapp/wails/issues/5043),
  [wails#6528](https://github.com/wailsapp/wails/issues/6528), and
  [wails#6300](https://github.com/wailsapp/wails/pull/6300)). Revisit it only if Rust
  becomes the deciding cost of Option E and those fixes land.
- **Other frameworks:**
  - Neutralinojs adds a second server and token API and builds no `.app`.
  - The webview/webview C library has no Edit menu, its `window.open` does nothing, and
    its last tag was in 2024.
  - wry and tao without Tauri need the same toolchain and give up the bundler and the
    updater.
  - Deno’s experimental `deno desktop` ships V8 just to launch Python.
  - Dioxus, Slint, Flutter, React Native macOS, MAUI, and Avalonia have the wrong shape
    or a heavy runtime.
  - Qt WebEngine, PySide6, and CEF used directly all bundle Chromium (PySide6 with
    WebEngine is about 1.3 GB installed).
  - Sciter uses a nonstandard engine under a proprietary license.
- **Frozen Python packagers:** PyInstaller 6.22, Nuitka 4.3, py2app 0.28, and Briefcase
  as the app builder all freeze the environment, which breaks entry-point plugin
  installs; Briefcase removes pip on purpose
  ([briefcase#419](https://github.com/beeware/briefcase/issues/419), open).
  A writable interpreter beside a frozen app means shipping a real interpreter anyway,
  so freezing buys nothing.
  Briefcase’s external-app mode remains a possible signing and DMG helper.
- **PyApp as the shell:** its first-run design (download Python, build a writable uv
  environment in Application Support) is right, but the environment is keyed to the
  version, so plugins vanish on upgrade; `self update` resolves from PyPI at run time
  instead of from a lock; and a `.app` wrapper loses Dock identity.
- **A script-only `.app`, Platypus, and an always-on LaunchAgent:** a script-only bundle
  cannot realistically be notarized or receive dropped folders; Homebrew disabled the
  Platypus cask on 2026-09-01; and an always-on loopback file server needs the token
  first and may be denied folder access silently.
- **A Rust rewrite of the server** (the August brief’s Option E): it breaks in-process
  Python plugins as designed, and the measured hot paths already run in Rust wheels.
  Performance work continues as native wheels under every option.

## Recommendations

1. **Adopt the layering as the architecture.** Record it in an architecture document
   shared by the macOS app and the VS Code host, add the new routes and flags to the
   parity map, and add the host-protocol row to the Standing Compatibility Answers.
2. **Build host mode first** (Layering item 1), with a reference host in the test suite.
   Every shell needs it.
3. **Build the runtime layer** (Layering items 2–4): the rootless runtime report, the
   plugin CLI mode for both install kinds, and the runtime builder.
4. **Gate the engine before writing a shell.** Re-measure each bound in
   [rendering large content](../../large-content-rendering.md) at its representative
   case in WKWebView, in back-to-back pairs against Chrome.
   Record this result separately from `mb-etqi`’s broader owner acceptance: its
   cross-browser behavior, private-auth and external-plugin checks remain required.
   WebKit passes if every pair is within 1.3x. If a bound fails, either make that bound
   engine-specific, a core change that also helps Safari users of the CLI today, or ship
   Option F.
5. **Ship Option D in two steps,** each usable on its own:
   1. **Use the CLI install.** The app discovers a CLI install, runs it, and serves
      settings from it. This needs no provisioning code, so it tests the shell and host
      mode early.
   2. **Add the app-managed runtime** with the uv-plus-Python-archive layout and the
      opt-in command-line launcher, keeping the signed bundled Python layout as the
      fallback if clean-Mac tests hit uv#16726 or the notary rejects the nested archive.
6. **Distribute** a notarized, stapled DMG and ZIP on GitHub Releases from a macOS CI
   job, and a cask in a personal Homebrew tap.
   Each Metabrowser release produces an app build with a new `pylock.toml`; start with
   cask upgrades and an in-app notice, and add Sparkle 2.10 or later when shell updates
   become routine.
7. **Write the project-plugin trust spec** before supporting project plugins.
8. **Decide the server lifetime and security model together, before step 5.2.** Client
   authentication, a boot id, and an owner-only state file help under every option, so
   they can land with host mode.
   Choosing between per-root servers with state files and one shared server with a
   browsing context needs the answers listed under Questions That Decide It and the open
   security questions; prototype the agent workflow through the skill on both before
   committing.
9. **Keep the CLI and the framework-free frontend** as they are.
10. **Revisit the shell choice** if a Windows or Linux app enters the near-term roadmap
    (Option E), and when Tauri 3’s CEF runtime is stable, Wails v3’s macOS window
    handling lands, or Electrobun gains signed updates.
    Add Option B only if the server ever serves several roots from one origin, as server
    Option S would.

## Next Steps

- [ ] Extract the decisions above into a plan under `docs/project/specs/active/`, as
  [Documentation](../../development.md#documentation) requires.
- [ ] Write the shared host and runtime architecture document, generalizing the VS Code
  draft’s server supervisor and uv resolver.
- [ ] Track Layering items 1–7 and the reference host as beads.
- [ ] Run and record the WebKit measurement gate; retain `mb-etqi` until its complete
  owner-acceptance scope passes.
- [ ] Spike step 1 of Option D against a CLI install, reusing paraverse’s lifecycle
  state machine; verify `window.print()` and drag-and-drop in WKWebView.
- [ ] Spike step 2 on a clean macOS 15 virtual machine without the Command Line Tools,
  Developer ID signed and notarized: DMG size, first-run time, privacy prompts for a
  child server, the `install_name_tool` prompt, and notarization of the bundled Python
  archive.
- [ ] Write the project-plugin trust spec.
- [ ] Prototype the skill-driven agent workflow against per-root servers with state
  files (P+) and against a shared server (S), and test whether an Open-panel folder
  grant reaches a child or login-item server.
- [ ] Measure a Seatbelt worker restart, including the event-stream reconnect, before
  choosing the restart model for a growing browsing context.
- [ ] Write a security-model decision record covering client authentication, the
  browsing context, and the Seatbelt worker.
- [ ] Add a macOS release job with signing secrets and a `notarytool` API key.
- [ ] Land the tbd desktop guideline refresh, a separate pull request in `jlevy/tbd`:
  Electron’s installed size and support window, Tauri’s security floor and shell-plugin
  behavior, Electrobun’s digest, uv’s signed binaries, when Python needs
  `disable-library-validation`, and new guidelines for macOS WebView shells and desktop
  Python runtimes.

## Methodology

The research ran as twelve independent tracks on 2026-11-08, each limited to primary
sources: official documentation, GitHub releases and source read at pinned tags, package
registries, and issue trackers.
Three independent reviews then checked the facts against those sources, the architecture
against the codebase, and the prose against the documentation guidelines.
Three further tracks covered the agent-controlled server: a code audit of live updates,
the registry, and the root model; precedents for discovery, attach, and live changes;
and security models, including Seatbelt and `open(2)` probes on macOS 26.5. Version
claims follow the cool-off.
Metabrowser facts come from the source at `e1cfca1a`. Experiments ran on a macOS 26.5
arm64 machine with full Xcode: uv layouts in an isolated lab with every uv directory
redirected, a 150-line AppKit and `WKWebView` probe, a pywebview launcher bundle, and a
scratch build of paraverse.
Not tested: a Mac without the Command Line Tools, a managed Mac, notarization of nested
archives, and privacy prompts for a child server under a Developer ID build.

## 2026-11-10 Addendum: Server Topology and Agent Handoff

[Server Topology, Lifecycle, and Agent Handoff for the Native App](research-2026-11-10-native-app-server-topology.md)
takes up the questions under Use Cases Under Exploration with code reading,
measurements, and platform probes.
What it adds to this brief:

- **Questions That Decide It:** per-root servers behind a registry (option P+, extended
  with a `present` verb and a `navigate` event).
  A server’s fixed cost measured about 65 MB and 1 s of CPU, and four started together
  were as fast as one.
  One shared process stays a later option: its two technical objections failed when
  measured, but it would save only that fixed cost per root.
- **S1–S3:** a server the app spawns is charged to the app (observed; a detached one was
  not tested). A server started from an agent’s shell is charged to the agent’s host,
  which under Claude Desktop is a versioned binary whose grants are lost on each update.
  Apple DTS says an `SMAppService` agent is charged to the app, and that a bare
  executable in `Contents/MacOS` worked where a separate helper bundle did not.
  Whether an Open-panel grant reaches a child is still untested.
- **Sandboxed agents:** no probed sandbox lets a shell command launch an app, and
  Codex’s default also blocks loopback, so the CLI runs outside the agent’s sandbox or
  behind an MCP adapter.
- **Threats:** WebKit landed a Local Network Access check in September 2026 that has no
  prompt yet, so a prompt decision is treated as denied
  ([bug 319907](https://bugs.webkit.org/show_bug.cgi?id=319907)); whether Safari ships
  it is unknown.
- **Cookie scope:** the per-instance cookie name this brief gives the session token
  (under What Metabrowser Requires of a Host and in layering item 1) prevents collisions
  but isolates nothing.
  A cookie ignores the port and `SameSite` treats two ports on one host as the same
  site, so a page can send it to every server on `127.0.0.1`. A separate web data store
  does not help, because it belongs to the requesting page.
  Nor does a host name per server, since a host-only cookie still goes to every port on
  that host. The later brief has host mode give every client, the app’s web views
  included, a token in the `Authorization` header that it sends only to its own origin,
  in place of any cookie.

## 2026-11-11 Addendum: The WebKit Measurement Gate

Recommendation 4’s gate was run in the app’s web view, in back-to-back pairs against
Chrome, and recorded in
[Measured in WebKit](../../large-content-rendering.md#measured-in-webkit) with its
method, machine, and versions.
What it changes here:

- **The gate failed.** From response to laid out, WebKit took 1.6 to 5.8 times Chrome’s
  time in the source view, 1.4 to 2.7 times in the binary view, and up to 1.5 times for
  highlighting and the diff layout switch.
  Its diagnostics point to a small core fix for the source view’s worst case, which
  appends each chunk as one text node, and to none for the others.
  So Recommendation 4’s fallback is open: an engine-specific bound, a core change that
  also helps Safari users of the CLI, or Option F. That choice is the owner’s.
- **Engine evidence is no longer Chromium-only** (What Metabrowser Requires of a Host),
  for the bounds the gate covers.
  WebKit used a seventh to a half of Chrome’s renderer memory, and its element-height
  limit is 33,554,428 CSS px, twice Chrome’s on a 2x display.
- **`window.print()` is now verified, and does nothing** in a `WKWebView` whose delegate
  does not implement WebKit’s private print methods; `printOperation(with:)`, run
  modally, prints the document.
  Option D’s list of what the shell must implement therefore includes the page’s own
  Print button.
- **Drag and drop:** a folder dropped on a page opens, and a dropped file is cancelled
  as a `file://` navigation.

The last two are observations from before jlevy/metabrowser#359, which fixed both: the
page’s Print button now reaches File > Print’s path (`mb-j3eu`), and a dropped file
opens at its page (`mb-3h2m`). A later check run, with the app’s print bridge in the
gate’s driver, found the Print request reaching that path and a dropped file handed to
the app’s open path
([`window.print()` and Drag and Drop](../../large-content-rendering.md#windowprint-and-drag-and-drop)).

## 2026-11-12 Addendum: Plugin Sources

Adding Plugins Without Rebuilding the App kept every Python plugin in a runtime’s own
environment and had the plugin mode reinstall Metabrowser with `--with`.
[Loading Plugins from Any Source](research-2026-11-12-plugin-sources.md) found that
install unresolvable for the motivating plugin, because of Metabrowser’s exact pins, and
the owner ruled out reinstalling Metabrowser to add a plugin.
[Plugin Sources and Out-of-Process Plugin Environments](../specs/active/plan-2026-11-12-plugin-sources.md)
replaces that section’s install mechanics and its project-plugin sketch: plugins are
registered sources or a trusted repository’s own, Python plugins run in workers on their
own interpreters, and an app-managed runtime no longer reinstalls plugins when its base
changes. What the section says about the signed bundle holding no plugins still holds.

## References

- Metabrowser: [Views, Models, and Routes](../architecture/arch-views-models-routes.md),
  [VS Code Extension Host](../architecture/arch-vscode-extension-host.md),
  [Plugin Authoring](../../plugins.md), [command line](../../command-line.md),
  [rendering large content](../../large-content-rendering.md),
  [Installation](../../installation.md), [Publishing](../../publishing.md),
  [Compatibility and Legacy Code](../../development.md#compatibility-and-legacy-code),
  [SECURITY.md](../../../SECURITY.md), and
  [supply-chain policy](../../../SUPPLY-CHAIN-SECURITY.md)
- Prior research:
  [Desktop App Packaging for Metabrowser](research-2026-08-16-desktop-app-packaging.md)
- tbd guidelines: `electron-app-development-patterns`, `tauri-app-development-patterns`,
  `electrobun-app-development-patterns`, `supply-chain-hardening`
- Apple:
  [Notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
  [TN3179](https://developer.apple.com/documentation/technotes/tn3179-understanding-local-network-privacy),
  [LSFileQuarantineEnabled](https://developer.apple.com/documentation/bundleresources/information-property-list/lsfilequarantineenabled),
  [WKWebView](https://developer.apple.com/documentation/webkit/wkwebview)
- uv and Python: [uv](https://github.com/astral-sh/uv),
  [python-build-standalone](https://github.com/astral-sh/python-build-standalone),
  [uv#14893](https://github.com/astral-sh/uv/issues/14893),
  [uv#16726](https://github.com/astral-sh/uv/issues/16726),
  [uv#21962](https://github.com/astral-sh/uv/pull/21962)
- Shells: [Tauri](https://github.com/tauri-apps/tauri),
  [Electron releases](https://releases.electronjs.org/),
  [Electrobun](https://github.com/blackboardsh/electrobun),
  [Wails](https://github.com/wailsapp/wails),
  [pywebview](https://github.com/r0x0r/pywebview),
  [Sparkle](https://sparkle-project.org/)
- Distribution: [Homebrew 5.0.0](https://brew.sh/2025/11/12/homebrew-5.0.0),
  [Acceptable Casks](https://docs.brew.sh/Acceptable-Casks)
- Precedents: [paraverse](https://github.com/jlevy/paraverse),
  [Comfy Desktop](https://github.com/Comfy-Org/Comfy-Desktop),
  [Datasette Desktop](https://github.com/simonw/datasette-app),
  [Open WebUI Desktop](https://github.com/open-webui/desktop),
  [Anki’s launcher removal](https://github.com/ankitects/anki/pull/5019),
  [Livebook’s Tauri desktop](https://github.com/livebook-dev/livebook/pull/3112),
  [Mu](https://github.com/mu-editor/mu), [Ollama](https://github.com/ollama/ollama)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
