# Metabrowser for macOS

**Status:** Spike. This is step 1 of Option D in the
[macOS app research brief](../../docs/project/research/research-2026-11-08-macos-app-packaging.md):
a hand-written Swift app that uses an existing command-line install of `metab`.

## What It Is

A native macOS app, written with AppKit and `WKWebView`, that finds your CLI install of
`metab`, starts one server per folder you open, and shows each folder in its own window.
It is a thin wrapper.
Everything Metabrowser shows comes from `metab`, the page talks to its server directly
over HTTP and server-sent events, and the page never calls a shell API. The app adds
only what a browser tab cannot give: a Dock icon, folders dropped on it or opened with
Open With, native menus and windows, and server lifetimes it controls.

It is not yet a distribution.
It installs nothing: no Python, no uv, no Metabrowser.
It has a [release pipeline](#building-a-release) (Developer ID signing, notarization, a
DMG, and a draft Homebrew cask) that has not yet made a release, a
[CI workflow](#continuous-integration) that builds, tests, and rehearses it, and no
updater or URL scheme.
It runs on arm64 Macs with macOS 26 or later.
[Gaps to Close](#gaps-to-close) maps what is missing to the brief.

## Build, Test, and Run

You need macOS 26 or later, Xcode 26 (Swift 6.3 or later), and a CLI install:

```shell
uv tool install metabrowser
```

From the repository root (each target delegates to `apps/macos/Makefile`, and each
prints a skip message on systems other than macOS):

```shell
make macos-test                      # unit tests (swift test) and the scripts' checks
make macos-app                       # build, assemble, and sign build/Metabrowser Dev.app
make macos-run FOLDER="$HOME/notes"  # build the app and open a folder with it
make macos-dmg                       # build/Metabrowser-Dev-0.1.0-arm64.dmg, checked
make macos-release                   # the official build; see Building a Release
make macos-notarize FILE=path        # notarize and staple one .app or .dmg
make macos-build                     # debug build only
make macos-clean                     # remove .build and build
```

`make verify` neither needs nor runs Swift, so Linux CI is unchanged; the app has its
own [macOS workflow](#continuous-integration).

`scripts/build-app.sh` builds a release binary, strips it, lays out the bundle, stamps
the variant’s identity and the version, copies the variant’s icon, and signs.
It signs ad hoc by default, which runs on this Mac only.
Set `SIGN_IDENTITY="Developer ID Application: Name (TEAMID)"` to sign with the hardened
runtime and a secure timestamp.
`BUILD`, `ARCHES` (for example `"arm64 x86_64"`), and `ICON=0` are documented in the
script.

### Versions

`VERSION` holds the version, `MAJOR.MINOR.PATCH`, and nothing overrides it; a release is
tagged `macos-v<VERSION>`. `CFBundleVersion` is the commit count of `HEAD`, so a shallow
clone is refused unless `BUILD` is set.
The app versions separately from the Python package, which it runs but does not contain.

### Variants

Every build is one of two variants, and the variant decides the bundle’s identity:

|  | dev | release |
| --- | --- | --- |
| Bundle | `build/Metabrowser Dev.app` | `build/Metabrowser.app` |
| Bundle identifier | `io.github.jlevy.metabrowser.dev` | `io.github.jlevy.metabrowser` |
| Icon | `Resources/AppIcon-Dev.icns`, the canary icon with a gold rim | `Resources/AppIcon.icns`, the published icon |
| URL schemes | each declared scheme with `-dev` (none yet) | as declared |
| DMG | `build/Metabrowser-Dev-<version>-arm64.dmg` | `build/Metabrowser-<version>-arm64.dmg` |

The rule: **the canary icon is for development builds, and the published icon only for
official releases.**

- **Every development build is dev**: `make app`, `make run`, `make dmg`, their
  `macos-*` forms, any ad hoc build, and every build CI uploads from a branch, a pull
  request, or `main`.
- **Only the release path builds release**: `make release`; its rehearsal, which CI runs
  on every change and never uploads; and a CI release job on a `macos-v*` tag, once one
  exists. An official build must be signed with a Developer ID, notarized, built from a
  commit, and carry the published icon; `make release` checks all four before it builds.
  `make release NOTARIZE=0` rehearses the same steps with an ad hoc signature and says
  it is a rehearsal.
- **Release only on request**: elsewhere, `VARIANT=release` on the `make` command line
  builds the release variant.
  A `VARIANT` exported in the environment is ignored, so a leftover export cannot turn a
  development build into a release build.
- **The canary icon never ships in a release**: `scripts/check-dmg.sh` refuses a release
  image that holds the canary icon or lacks the published one, and a development image
  that holds the published icon.
  `scripts/build-app.sh` stops when the variant’s icon is missing from `Resources/`.

A separate identity is what lets a development build run beside an installed release:
two copies with one bundle identifier share user defaults, privacy grants, and
LaunchServices registration, and a URL scheme claimed twice has no defined target.
`scripts/build-icon.sh` regenerates both icons from the masters in `AppIcon/`; see
[AppIcon/README.md](AppIcon/README.md).

To run the tests against a real server too:

```shell
cd apps/macos
METABROWSER_SHELL_TEST_METAB=$HOME/.local/bin/metab swift test
```

Where to look while it runs:

- **Server log:** `~/Library/Logs/Metabrowser/<folder>-<hash>.log`, mode 0600. It holds
  the server’s output, with the app’s lifecycle events interleaved: start command, pid,
  announced URL, readiness time, stop, and exit status.
  File > Reveal Server Log opens it.
- **App log:** `log stream --predicate 'subsystem == "io.github.jlevy.metabrowser.dev"'`
  for a development build; the subsystem is the bundle identifier, so a release build
  logs as `io.github.jlevy.metabrowser`.
- **Web Inspector:** Safari’s Develop menu, in debug builds or after
  `defaults write io.github.jlevy.metabrowser.dev WebInspectorEnabled -bool true`.
- **Start over:** `defaults delete io.github.jlevy.metabrowser.dev` forgets the saved
  runtime and the recent folders, so the next launch runs discovery again.
  Each variant has its own defaults domain, named by its bundle identifier.

### Continuous Integration

`.github/workflows/macos-app.yml` runs on pushes to `main` and on every pull request
that changes `apps/macos`, the root `Makefile`, or the workflow.
It uses no secrets and signs only ad hoc.
It runs on one pinned runner image, with its Xcode selected explicitly:

| Runner | Xcode | Why | Runs |
| --- | --- | --- | --- |
| `macos-26` | 26.6 (Swift 6.3) | The toolchain the app is built with, on the oldest macOS it supports | Every step below |

1. `make install`, after setting up uv, Python, and Node as `ci.yml` does.
2. `make macos-test` with `METABROWSER_SHELL_TEST_METAB` set to that environment’s
   `metab`, so the live tests run against the server this checkout locks.
   The step fails unless `LiveMetabTests` ran and passed.
3. `make macos-app`.
4. `make macos-dmg` and `make macos-release NOTARIZE=0`, then `scripts/check-dmg.sh` on
   both images.
5. The development app, zipped with `ditto`, and the development image, uploaded as
   artifacts kept for 7 days.
   The rehearsal’s image carries the published icon on an ad hoc signature, so it is
   checked and never uploaded.
   Like any ad hoc build, a downloaded artifact runs only after Open Anyway (see
   [What a Downloader Experiences](#what-a-downloader-experiences)).

The same steps on a Mac, from the repository root:

```shell
make install
METABROWSER_SHELL_TEST_METAB="$PWD/.venv/bin/metab" make macos-test
make macos-app
make macos-dmg                 # checks its image with scripts/check-dmg.sh
make macos-release NOTARIZE=0  # the rehearsal, which checks its image too
```

## Building a Release

A release is one command, `make macos-release`, and it uses only Apple’s tools: `swift`,
`codesign`, `ditto`, `hdiutil`, `xcrun notarytool`, `xcrun stapler`, and `spctl`. No
release has been made yet; the pipeline has run end to end with an ad hoc signature and
the notarization steps skipped.

### Once per Mac

1. **A Developer ID Application certificate**, with its private key, in the login
   keychain. It needs the Apple Developer Program, and only the account holder can create
   one. `security find-identity -v -p codesigning` lists it as
   `Developer ID Application: Name (TEAMID)`.

2. **Notary credentials in the keychain**, saved once under a profile name, so no secret
   appears in a command line or an environment:

   ```shell
   xcrun notarytool store-credentials metabrowser-notary \
     --key AuthKey_KEYID.p8 --key-id KEYID --issuer ISSUER_UUID
   ```

   That is an App Store Connect API key; `--apple-id`, `--team-id`, and an app-specific
   password work too.

3. **The published icon**, `Resources/AppIcon.icns`, committed.

### Each Release

```shell
echo 0.1.0 > apps/macos/VERSION
git commit -m "release(macos): 0.1.0" apps/macos/VERSION
git tag -a macos-v0.1.0 -m "Metabrowser for macOS 0.1.0"
make macos-release SIGN_IDENTITY="Developer ID Application: Name (TEAMID)" \
  APPLE_KEYCHAIN_PROFILE=metabrowser-notary
```

`scripts/release.sh` then runs, stopping at the first failure:

1. **Preflight:** the identity is in the keychain, the notary credentials are set, the
   published icon exists, and `apps/macos` has no uncommitted changes.
2. **App:** `build-app.sh` builds and signs it with the hardened runtime and a secure
   timestamp, inside out and never with `--deep`, and refuses any entitlement and any
   signature whose entitlements `codesign` cannot read.
3. **App notarization:** `notarize.sh` zips the app with `ditto`, submits it with
   `notarytool submit --wait`, saves the notary log as
   `build/notary-Metabrowser.app.json` (read it for warnings even after an Accepted
   verdict), staples the ticket to the app, and runs `spctl --assess --type execute`. A
   stapled app opens without reaching Apple, also after it is dragged out of the image.
4. **Image:** `make-dmg.sh` stages the app, an `Applications` link, and the app’s icon
   as `.VolumeIcon.icns`, creates a read-write image to set the volume’s custom-icon
   flag, converts it to a compressed UDZO image, signs it, and writes its checksum.
5. **Image notarization:** the image is submitted, stapled, and assessed with
   `spctl --assess --type open`, and its checksum is written again, since stapling
   changes it.
6. **Check:** `check-dmg.sh` checks the image as a downloader meets it (see
   [Variants](#variants) for the icon rule).
7. **Cask:** `build/metabrowser-app.rb`, the cask template in `packaging/` with the
   version, the checksum, and the image’s architecture filled in: `-arm64.dmg` declares
   `depends_on arch: :arm64`, `-x86_64.dmg` declares `:x86_64`, and `-universal.dmg`
   (`ARCHES="arm64 x86_64"`) declares none.
   The release stops if the cask’s URL would name another image than the one
   checksummed.

The outputs, at 0.1.0:

| File | Size |
| --- | --- |
| `build/Metabrowser.app` | about 0.9 MB |
| `build/Metabrowser-0.1.0-arm64.dmg` | about 0.5 MB |
| `build/Metabrowser-0.1.0-arm64.dmg.sha256` | one `shasum -a 256` line |
| `build/metabrowser-app.rb` | the cask |
| `build/notary-*.json` | the notary logs |

Apple says most submissions finish within 5 minutes; `NOTARY_TIMEOUT` (default `30m`)
bounds the wait.
`make macos-notarize FILE=build/Metabrowser-0.1.0-arm64.dmg` retries one
step. `make macos-release NOTARIZE=0` rehearses every step without credentials.

To publish, push the tag and attach the image and its checksum to a draft release, then
review the draft and publish it:

```shell
git push origin macos-v0.1.0
gh release create macos-v0.1.0 --draft --verify-tag --latest=false \
  --title "Metabrowser for macOS 0.1.0" \
  apps/macos/build/Metabrowser-0.1.0-arm64.dmg \
  apps/macos/build/Metabrowser-0.1.0-arm64.dmg.sha256
```

`--latest=false` keeps the Python package’s release as the repository’s latest.
Then copy `build/metabrowser-app.rb` to `Casks/` in a personal tap.
Publishing the release does not publish to PyPI: `publish.yml` runs its job only for a
`v` tag, the Python package’s. No workflow builds, signs, or drafts the release yet (see
[Gaps to Close](#gaps-to-close)).

### What a Downloader Experiences

With a signed, notarized, and stapled release:

1. **Download.** The browser marks the DMG with `com.apple.quarantine`, which is what
   makes Gatekeeper check it.
   `shasum -a 256 -c Metabrowser-0.1.0-arm64.dmg.sha256` checks the download.
2. **Open the DMG.** Gatekeeper checks the image’s signature and stapled ticket, and a
   window shows Metabrowser and Applications; the volume carries the app’s icon.
   Finder arranges the two icons itself, since the image has no window layout yet.
   Drag Metabrowser to Applications.
3. **First launch.** Gatekeeper checks the Developer ID signature and the stapled
   ticket, which needs no network, and asks once whether to open an app downloaded from
   the Internet, saying Apple checked it for malicious software.
   An app opened straight from the DMG or from Downloads runs from a randomized
   read-only copy (App Translocation); it works, but belongs in Applications.
4. **Runtime.** The app runs the `metab` command-line tool and does not yet install it.
   Without one, the first launch shows the install command,
   `uv tool install metabrowser`, and every place it looked, and Find Again picks up the
   new install.
5. **Privacy prompts.** Opening a folder in Desktop, Documents, Downloads, iCloud Drive,
   or on a removable or network volume asks once, in Metabrowser’s name, because the app
   is responsible for the server it starts.
   A Git remote on the local network can ask for Local Network access.

With Homebrew, `brew install --cask jlevy/tap/metabrowser-app` downloads the same image,
quarantines it, and installs the app, so the first launch is the same; updates come from
`brew upgrade --cask`, as the app has no updater.

A development or rehearsal DMG is signed ad hoc.
It runs on the Mac that built it, but on any Mac that downloads it, CI artifacts
included, Gatekeeper refuses it as unverifiable, and since macOS 15 only Open Anyway, in
the Privacy & Security pane of System Settings, overrides that.
Do not hand one out as a release.

## Architecture

| Path | Holds |
| --- | --- |
| `Package.swift` | SwiftPM only: no Xcode project and no package dependencies. Swift 6 language mode with main-actor default isolation. |
| `Sources/ShellCore/Supervision/` | Spawning a server, recognizing it as ready, and stopping it. |
| `Sources/ShellCore/Runtime/` | Finding `metab`, the child environment, short commands, and saved settings. |
| `Sources/ShellCore/{Logs,Folders,Web}/` | Server logs, recent folders, folder identity and window titles, the navigation policy, the web view configuration, and downloads. |
| `Sources/Metabrowser/` | The AppKit app: lifecycle, menus, folder sessions, windows, and the SwiftUI status and settings views. |
| `Tests/ShellCoreTests/` | Swift Testing tests of everything in `ShellCore`, with fake processes and fake machines, plus the real `posix_spawn` path with `/bin/sh` children and real `WKDownload`s from a local server. |
| `Resources/Info.plist` | The bundle’s property list. |
| `AppIcon/`, `scripts/build-icon.sh`, `Resources/AppIcon*.icns` | The app icon’s SVG masters and renderer, and the icons they build: `AppIcon.icns` for official builds and `AppIcon-Dev.icns` for development builds. See [AppIcon/README.md](AppIcon/README.md). |
| `VERSION` | The app’s version, set nowhere else. |
| `scripts/build-app.sh`, `scripts/common.sh`, `scripts/test-scripts.sh` | The bundle script, the variants and helpers every script shares, and the tests of those helpers that `make test` runs. |
| `scripts/release.sh`, `notarize.sh`, `make-dmg.sh`, `check-dmg.sh` | The release pipeline and its steps. |
| `packaging/metabrowser-app.rb.template` | The Homebrew cask, filled in by each release. |

`ShellCore` holds everything that can be tested without a window; it imports no AppKit.
It imports WebKit only for what its tests can run in a `WKWebView` without a window: the
web view’s configuration and downloads.
The app target is the platform behavior the brief exempts from the CLI parity rule:
finding a runtime before one exists, windows, menus, the Dock, and file events.

### A Folder’s Server

1. **Open.** File > Open Folder, File > Open Recent, a drop on the Dock icon or on a
   window, Open With, and `open -a Metabrowser.app FOLDER` all arrive at one method.
   The folder’s canonical path keys one session, so one root has one server and one
   window (plus any tabs the page opens).
2. **Spawn.** `ServerSupervisor` runs
   `metab ROOT --no-open --host 127.0.0.1 --port 8411` with `posix_spawn`: in its own
   process group (`POSIX_SPAWN_SETPGROUP`), with only the descriptors it is given
   (`POSIX_SPAWN_CLOEXEC_DEFAULT`), with default signal handling restored, and with the
   folder as its working directory, so `.env` lookup matches `metab .` in Terminal.
   Its stderr is the server log itself, opened before the spawn, so an app that stalls
   cannot block the server through a full pipe.
   Its stdout is a pipe the app reads for the announcement and appends to the log.
   A log that cannot be prepared, opened, or rotated fails the launch with its path and
   cause, and a log write that fails midway says so in the window’s output.
   Its stdin is a pipe the app holds open, ready to become the parent-death signal.
3. **Ready.** The server prints `Serving ROOT at http://127.0.0.1:PORT/view/` before its
   socket listens, so the supervisor parses that line and then polls the URL for a 2xx,
   within 60 seconds. The line must start with `Serving ` and end with the URL, and a
   folder whose path contains a line break is refused, since its name could forge the
   line; the JSON ready line of host mode removes this class of problem.
   `LaunchGate` lets one server start at a time, because `metab` chooses its port by
   probing and binds later, so two servers starting together could choose the same port.
4. **Show.** The window loads the URL in a `WKWebView` with the persistent default
   website data store, because Metabrowser keeps preferences in host-only cookies.
   A native “Starting” view covers the window until the page commits; its spinner
   appears only after 300 ms.
5. **Check.** A window that joins a running server (a Command-click, and a folder opened
   again or brought back from the Dock) first asks the server for its entry page, since
   a live pid is not a working server.
   A server that gives no 2xx within 5 seconds is hung, not busy: `GET /view/` measured
   12 to 61 ms (see `SupervisorPolicy.healthDeadline`). It is stopped, and fails.
   `target=_blank` windows are exempt: WebKit loads them at once, from a page the server
   just answered.
6. **Fail.** If the server exits, never announces itself, never answers, or stops
   answering, the window shows the reason, the last lines of output (stdout and stderr,
   read from this run’s part of the log), Retry, Reveal Logs, and Runtime Settings.
   Nothing restarts automatically.
   After Retry, each window returns to the page it showed, on the new port.
7. **Stop.** Closing a folder’s last window stops its server: SIGTERM to the process
   group, up to 5 seconds, then SIGKILL, up to 2 more seconds (a process stuck in
   uninterruptible I/O, such as a hung network mount, ignores even SIGKILL, and quit
   must not wait on it), then SIGKILL to anything left in the group.
   The server is reaped only after that last signal: until then its exited process keeps
   its pid, which is also the group’s id, so no signal can reach another process that
   was given the same id.
   Quitting stops every server, including servers of windows closed moments before,
   before the app exits, also when the quit comes from SIGTERM, SIGINT, or SIGHUP sent
   to the app.

Every child is ended by one tracked termination, whoever asks for it: a stop, a restart,
a newer launch, or a start that gave up.
A stop waits for all of them, and a launch first waits for any left by the launch it
replaced, so overlapping restarts cannot drop a running child.
A restart launches only if nothing newer arrived while its old child stopped, and a
folder whose last window closed is shut down for good, so closing that window during a
restart leaves no server running.
`ServerFleet` holds the open and still-stopping servers for the app delegate, which is
how its quit ordering is tested.

`ServerLaunch` is the seam for the brief’s host mode.
It owns the arguments, the stdin line, the readiness parser, the readiness URL, and the
authorization a window installs before loading (`WebAuthorization.cookie`).
`CLIServeLaunch` implements it for today’s server; a host-mode launch replaces it
without changing the supervisor or the windows.

### Finding the Runtime

Setup runs on the first launch, and again from Settings > Find Again.
It looks in this order and runs `metab --version` on each candidate that exists:

1. the path saved by a previous setup;
2. `METABROWSER_METAB`;
3. `~/.local/bin/metab`;
4. uv’s tool bin directory (`UV_TOOL_BIN_DIR`, `XDG_BIN_HOME`, `XDG_DATA_HOME/../bin`,
   or `~/.local/bin`, as uv documents);
5. `/opt/homebrew/bin` and `/usr/local/bin`;
6. the `PATH` of your login shell.

The login shell comes last and runs only when the earlier locations miss `metab`, `git`,
or `gh`. It runs your shell startup files in the app’s name, which can take seconds and
can raise privacy prompts you never saw in Terminal.
One install reached two ways is tried once.
Setup saves the runtime and the absolute paths of `git` and `gh`; later launches only
check that the saved `metab` is still executable, so they start no extra process.
If nothing is found, Settings shows the install command and every place it looked.
Settings also chooses another `metab` with an open panel, runs `metab --doctor`, and
reveals the logs folder.
The runtime chosen there or found by Find Again is what folders opened afterwards start,
and what an open folder starts at its next Retry or File > Restart Server; until then,
open folders keep their servers.
When Find Again and a choice overlap, the one started last wins: a search that finishes
after a newer choice changes nothing.
A Find Again that finds nothing leaves no runtime, saved or in use, so neither the next
folder nor the next launch starts the `metab` that failed; the next folder waits for a
runtime.

### The Child’s Environment

The server’s environment is built from an allowlist, never inherited.
It keeps `HOME`, `USER`, `LOGNAME`, `TMPDIR`, locale names, `SSH_AUTH_SOCK` (`metab`
runs Git over ssh in batch mode, so ssh remotes need the agent), and the proxy variables
`HTTP_PROXY`, `HTTPS_PROXY`, `NO_PROXY`, and `ALL_PROXY` in either case, and sets:

- `PATH` to the directories of the `git` and `gh` found at setup, then
  `/usr/bin:/bin:/usr/sbin:/sbin`. A Finder launch would otherwise give the server
  Apple’s `git` shim and no `gh`.
- `PYTHONNOUSERSITE=1`, so packages in `~/.local/lib/python*` cannot shadow the
  server’s.
- `PYTHONUNBUFFERED=1`, so the log is current.

Nothing else passes: no `UV_*`, `VIRTUAL_ENV`, `PYTHONHOME`, or `PYTHONPATH` from a
Terminal launch.

### The Window

- **Title:** the folder’s short name in bold, then a bullet and “Metabrowser” in a
  secondary style (`fdu • Metabrowser`), so each window says at a glance which folder it
  shows. The names come from `GET /api/identity`, asked once the server is ready.
  Until then, and from a `metab` without the route, the window names the folder from its
  path as `metab` would (`FolderIdentity.localFolder`). `window.title` holds the plain
  text, which the Window menu, Mission Control, the Dock, and accessibility read.
  A tab shows the short name, with the full name as its tooltip, and the title’s tooltip
  and `window.subtitle` give the full name and kind (`~/wrk/github/fdu · Local folder`).
  The page’s `<title>` is not used.
- **Navigation:** the server’s origin (scheme, host, and port) stays in the window.
  A clicked link to another `http`, `https`, or `mailto` URL opens in the default
  browser; the same URL reached by script, redirect, form, or Back and Forward is
  cancelled, so a page cannot open the browser by itself, and Back to a page of a server
  that restarted on another port does nothing.
  `file://` and other schemes are cancelled.
  `target=_blank`, `window.open`, and Command-click on links to the same server open a
  new tab of the folder’s window.
  A page opens one only on a user gesture: the configuration turns
  `javaScriptCanOpenWindowsAutomatically` off, which macOS leaves on, so a previewed
  HTML file cannot open tabs by itself.
- **Downloads:** `WKDownload` with a save panel that opens in Downloads.
  Choosing the destination is user intent, so no Downloads privacy prompt appears.
  A confirmed Replace keeps the existing file until the new one is complete:
  `WKDownload` refuses a destination that exists, so the download goes to a staging file
  on the same volume and is renamed over the original when it finishes
  (`StagedDownload`). A download that fails leaves the original as it was, and an alert
  says so.
- **Browser features:** Back and Forward (Command-\[ and Command-\]), Reload, zoom
  (persisted), Print through `printOperation`, Find through `NSTextFinder` with a find
  bar container, JavaScript `alert`, `confirm`, and `prompt` as sheets, and file inputs.
  If the web content process dies, the window reloads, at most twice in 30 seconds, and
  then shows the status view.

### Why the Title Is a Title-Bar Accessory

AppKit draws a system title in one font and one color, so the window hides it
(`titleVisibility = .hidden`) and draws its own in a leading title-bar accessory,
`TitleAccessoryController`. Measured on macOS 26.5:

- **It sits where the system title sits.** macOS 26 puts a plain window’s title at the
  leading edge, after the window buttons: the proxy icon at x 82 and the text at x 100,
  in the 13-point title-bar font.
  A leading accessory starts at x 78, so the drawn title lands on the same points in the
  same font, and the title bar stays 32 points tall.
  AppKit places accessories for tabs, full screen, and right-to-left layouts.
- **A toolbar was the alternative.** A centered toolbar item makes the title bar 40 to
  76 points tall, centers the title where macOS 26 no longer puts it, and, with the
  title hidden, AppKit shows no proxy icon there either.
- **The accessory draws the proxy icon.** AppKit drops the proxy icon when a leading
  accessory is present, so the accessory draws one for a local folder, from
  `representedURL`. Dragging it copies or aliases the folder, never moves it, since a
  move would pull the folder out from under its server.
  Command-click or right-click on the icon or the title opens the path menu.
  A cached mirror has neither.
- **It behaves like a system title.** It dims when its window is not the main window of
  the active app (the tertiary label color, which an inactive system title measured
  close to), follows light and dark mode through label colors, and passes plain clicks
  to the title bar, which drags and double-clicks the window.
  In a narrow window, “• Metabrowser” goes first and whole, then the short name
  truncates (`WindowTitle.segments(fitting:)`).

### Pitfalls Found in the Live Run

Two defects only appeared when the built app was quit with SIGTERM, and both orphaned
the server. Each fix is commented at the code that would bring it back.

- **Quit from a dispatch handler deadlocks.** `.terminateLater` spins a nested run loop
  until the servers stop, and that loop cannot drain the main dispatch queue while one
  of the queue’s own blocks is on the stack.
  The signal handler therefore schedules the quit with `CFRunLoopPerformBlock`.
- **Main-actor default isolation traps off the main queue.** A Dispatch handler closure
  written in a main-actor context is inferred main-actor, and Swift 6’s runtime check
  raises SIGTRAP when it runs on another queue.
  Handlers for other queues must be marked `@Sendable`.

### Coding Guidelines

The app follows tbd’s language-neutral guidelines (tbd has no Swift guideline): general
coding and comment rules, error handling, testing and TDD, filesystem rules, release
engineering, supply-chain hardening, and backward compatibility.
Decision logic lives in `ShellCore` with tests, and the app target only connects it to
AppKit and WebKit. What is left as it is, on purpose:

- **Code the next milestone steps replace.** `AppDelegate.request(_:)` decides whether a
  dropped or opened URL is served, and `DropAwareWebView` accepts only folders; opening
  a file (`mb-tssz`) rewrites both.
  The File > Open Recent menu and its `RecentFolders` list give way to the system’s
  recent documents (`mb-cqxd`).
- **Errors ignored with a reason.** Each remaining `try?` names why at its line: a
  readiness probe that fails means not ready yet; the stdin line can fail only once the
  child has exited, and that exit is reported; a saved setup this build cannot read
  counts as none, so setup runs again; an unreadable volume ends the path menu at `/`;
  and a staging directory left after a failed download is in the volume’s temporary
  items, which macOS empties.
- **Layout numbers in views.** SwiftUI paddings and spacings stay inline, as SwiftUI
  code reads; numbers that set behavior (timeouts, limits, window and zoom sizes) are
  named and say why.
- **Regression tests name their defect.** A test written for a review finding says what
  the code used to do, since that defect is why the test exists.

## Why It Lives in This Repository

The app lives here, in `apps/macos`, rather than in a repository of its own:

- **The host protocol is a contract between the app and `metab`.** Its next steps (port
  0, a ready line, a stdin token, `/healthz`) change the server and the shell together.
  In one repository each change, its reference host, and the shell that consumes it land
  in one commit, as `docs/development.md` asks of internal contracts.
- **Releases stay coupled.** Each Metabrowser release will produce an app build with its
  own lock for the app-managed runtime.
- **Shells sit side by side.** The drafted
  [VS Code host](../../docs/project/architecture/arch-vscode-extension-host.md) would
  live beside it as `apps/vscode`, sharing the host protocol, docs, and issue tracker.

Nothing here ships to PyPI: `/apps/` is excluded from the sdist in `pyproject.toml`, and
`devtools/check_distribution.py` fails the build if an `apps` path reaches the sdist or
wheel.

A separate repository would make sense if the app gained its own release cadence (shell
updates through Sparkle that do not follow Metabrowser releases), needed signing secrets
that should not reach this repository’s CI, or had to support several Metabrowser
versions through a published host protocol.
Then the CLI install would be an external consumer, and the protocol a versioned
boundary with its own compatibility rules.

## Gaps to Close

Each gap points to the part of the brief that closes it.

| Gap | The spike today | Brief |
| --- | --- | --- |
| **Session token and cookie exchange** | None: like the CLI, the server answers any local process. `WebAuthorization.cookie` is the slot. | Layering item 1; Security Models |
| **Port 0 and a JSON ready line** | Ports walk up from 8411; the `Serving` line is parsed and the URL polled; `LaunchGate` serializes starts. | Layering item 1 |
| **Exit on stdin EOF** | The stdin pipe is held open, but today’s server ignores it, so a crashed or force-quit app orphans its servers until they are stopped by hand; an orderly quit does not. An interim option is a pidfile per server and reaping stale groups at the next launch, which needs a start-time check against pid reuse; it is not implemented. | Layering item 1 |
| **Descendants in other groups** | The group kill reaches only the server’s own process group. Git and `gh` run in their own groups, which the server ends on its graceful path; a server that needs SIGKILL leaves them running. | Layering item 1 (bounded shutdown that ends those groups) |
| **`/healthz`** | Readiness, and the health check before a window joins a running server, poll the `/view/` entry page. | Layering item 1 |
| **Identity from an older `metab`** | metab 0.12.0 has no `/api/identity`. On its 404 the window keeps the name it derives from the folder’s path, because a CLI install updates independently of the app. Remove the fallback once the app requires a `metab` with the route. | Folder identity (`mb-n9p6`) |
| **Rootless runtime report** | `metab --version` validates; `--doctor` output is shown as text. | Layering item 2 |
| **Explicit tool paths** | `git` and `gh` are found by their directories on `PATH`. | Layering item 5 |
| **Privacy-safe I/O** | Usage descriptions are declared; a protected folder prompts in the app’s name with no in-app guidance. | Layering item 6; macOS Platform Rules |
| **Settings served by Metabrowser** | A native Settings window. | Layering item 7 |
| **App-managed runtime** | None: a CLI install is required. | Recommendation 5.2; Wrapping uv |
| **First real release** | The release pipeline has run only with an ad hoc signature; no Developer ID build has been notarized. | Recommendation 6 |
| **Updates** | None: `brew upgrade --cask`, no in-app notice, no Sparkle, and no refusal of translocated launches. | Recommendation 6; Updates |
| **DMG window layout** | Finder places the two icons itself. A fixed layout needs a `.DS_Store` in the image, which Apple’s tools cannot write; Finder scripting needs a GUI session and an Automation grant, so it is not reproducible in CI. | Recommendation 6 |
| **Variant gaps in the app** | Both variants write server logs to `~/Library/Logs/Metabrowser/`, so they share a folder’s log if both serve it, and the menu items say “Metabrowser” in the dev build. | Not in the brief (`mb-9xl0`) |
| **WebKit measurement gate** | Not run. Large-content bounds were measured in Chrome; `window.print()` and drag and drop are not yet checked by hand. | Recommendation 4 (`mb-etqi`) |
| **Multi-root and attach** | One server per root; no attaching to an agent’s server, no state files, no `metabrowser://` hand-off from the CLI. | Use Cases Under Exploration; Sharing an Installation |
| **Release CI** | `macos-app.yml` builds, tests, and rehearses the release with an ad hoc signature. No job signs and notarizes from secrets or drafts a release on a `macos-v*` tag, so a release is built by hand (`mb-e9fm`). | Next Steps |

## Known Limitations

- Only folders open; a dropped file shows an alert.
- Closing a folder’s last window stops its server, so reopening it starts a new one.
- A restarted server comes back on a new port, and local storage is per origin, as with
  the CLI.
- State-home variables (`XDG_CACHE_HOME`, `METABROWSER_CACHE_DIR`, and the rest) are not
  passed to the server, so the app always uses the default homes.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
