# Metabrowser for macOS

**Status:** Alpha preview: a development build, built from source and not yet a signed
or notarized release, and it may change.
This is step 1 of Option D in the
[macOS app research brief](../../docs/project/research/research-2026-11-08-macos-app-packaging.md):
a hand-written Swift app that uses an existing command-line install of `metab`.

## What It Is

A native macOS app, written with AppKit and `WKWebView`, that finds your CLI install of
`metab`, starts one server per folder you open, and shows each folder in its own window
or tab. It is a thin wrapper.
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

You need macOS 26 or later, Xcode 26 (Swift 6.3 or later), and a `metab` the app
accepts, 0.12.1 or later ([The Version It Requires](#the-version-it-requires)). Until
0.12.1 is published, that is a source checkout’s: `make install` at the repository root
builds `.venv/bin/metab`, and Settings > Choose metab… points the app at it (so does
`open --env METABROWSER_METAB=…`). Once 0.12.1 is published, a CLI install does:

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
METABROWSER_SHELL_TEST_METAB="$PWD/.venv/bin/metab" make macos-test
```

The live tests check that `metab` against the version the app requires, so it must be
0.12.1 or later.

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
  runtime and the window preferences, so the next launch runs discovery again.
  Each variant has its own defaults domain, named by its bundle identifier.
  Deleting `~/Library/Application Support/io.github.jlevy.metabrowser.dev/session.json`
  forgets the last session, and File > Open Recent > Clear Menu the recent folders,
  which macOS keeps.

### Checking Files, Tabs, Recents, and Restore by Hand

The decisions behind these are tested in `ShellCore`; what AppKit and macOS do with them
is checked against the built app.
Set `APP` to the development build and make some folders:

```shell
APP="$PWD/apps/macos/build/Metabrowser Dev.app"
LOGS="$HOME/Library/Logs/Metabrowser"
mkdir -p /tmp/mb-check/{a/sub,b,c,d,e} "$HOME/Documents/mb-check"
echo '# notes' > /tmp/mb-check/a/notes.md; echo '# deep' > /tmp/mb-check/a/sub/deep.md
log stream --predicate 'subsystem == "io.github.jlevy.metabrowser.dev"' &  # the app log
```

1. **A file.** `open -a "$APP" /tmp/mb-check/a/notes.md` opens a window for `a` showing
   `notes.md`. `open -a "$APP" /tmp/mb-check/a/sub/deep.md` shows `deep.md` in that same
   window, and `pgrep -fl 'metab /private/tmp/mb-check'` still lists one server.
   `open -a "$APP" /dev/null` shows an alert.
   File > Open… chooses a file too.
2. **Recents.** After opening `b`, File > Open Recent and the Dock icon’s menu list `b`
   above `a`; Clear Menu empties both.
   `defaults read io.github.jlevy.metabrowser.dev` shows no `recentFolders` key.
3. **Tabs.** With Settings > Open folders in set to Tabs, opening `c` and `d` adds them
   as tabs of the front window; set to Windows, opening `e` gives it a window, and
   Window > Merge All Windows then merges every folder into one window.
   With the setting on System Settings and Desktop & Dock > “Prefer tabs when opening
   documents” at Always, a new folder opens as a tab.
4. **Discarded pages.** With `a` to `e` as tabs of one window, select each in turn: the
   app log says “discarding the page of background tab” for the tab shown longest ago
   once four tabs are in the background, and
   `ps -axo pid,command | grep -c '[W]ebContent'` drops by one.
   Selecting that tab reloads its page, with no “Starting” text, at the top of the page
   and with no Back or Forward history, since a discarded tab keeps only its address.
5. **Restore.** Make one window with tabs `a` and `b`, `b` selected, and a second window
   with `c`, and quit. `session.json` (see Start over) now lists them; the next launch
   logs “restoring 2 window(s): 3 server(s) to start”, the windows and tabs come back,
   and `grep -h 'starting:' "$LOGS"/{a,b,c}-*.log` with its timestamps shows `b` started
   first, then `c`, then `a`, each after the one before it was ready.
6. **Protected locations.** Add `~/Documents/mb-check` as a background tab, quit, and
   launch again: that tab says Metabrowser opens it when you select it, and
   `pgrep -fl 'Documents/mb-check'` finds no server until you select the tab.
   Once Documents access is granted, no prompt appears either way.
   To see that the restore raises none, the person at the Mac first resets that grant
   (`tccutil reset SystemPolicyDocumentsFolder io.github.jlevy.metabrowser.dev`) and
   then checks that the prompt waits for the tab’s selection: the waiting tab still
   shows the folder’s name and icon, and whether reading those can prompt is untested.
7. **Off, and empty.** With Settings > “Reopen the last session’s folders when
   Metabrowser opens” off, a launch restores nothing.
   With it on, closing every window before quitting restores nothing.
   After each quit, `pgrep -fl 'metab /private/tmp/mb-check'` finds nothing.

### Checking the Setup Flows by Hand

What a new user sees first is a window, which no unit test reaches.
`scripts/check-setup-flows.sh` sets up each case on the built development app, says what
to look for, and waits for Return between steps:

```shell
make install && make macos-app   # at the repository root
cd apps/macos
scripts/check-setup-flows.sh no-metab
scripts/check-setup-flows.sh old-metab
scripts/check-setup-flows.sh disk-image
```

Each run copies the app under its own bundle identifier,
`io.github.jlevy.metabrowser.setupcheck`, so it never touches the development app’s
saved runtime, recents, saved session, or LaunchServices entry, and opens it with a
scratch `HOME`. A scratch `HOME` hides only what is under it: discovery and the
first-run screen still look in `/opt/homebrew/bin`, `/usr/local/bin`, and on the login
shell’s `PATH`, which with the scratch `HOME` is the system’s own (`/etc/paths` and
`/etc/paths.d`). So the script refuses to run where a `metab` in any of those would be
found, and `no-metab` also where a uv in one would; on a Mac with Homebrew’s uv,
`no-metab` cannot run, and `old-metab` covers the screen with uv.
It downloads and installs nothing: “installing” uv or `metab` links the uv on `PATH` and
this checkout’s `.venv/bin/metab` into the scratch `~/.local/bin`. On exit it quits the
copy with SIGTERM, detaches its image, unregisters the copy, and deletes its defaults,
saved session, and recents.
A copy that needs SIGKILL, a server left running, and a server started from the older
`metab` in `old-metab` are each a failed check: the script finishes its cleanup, then
exits nonzero, keeping an earlier nonzero status if it had one.
`scripts/test-scripts.sh` checks that accounting, and that every script starts with its
interpreter line, on stand-in processes.

| Case | What it checks |
| --- | --- |
| `no-metab` | No uv and no `metab`: the uv install and the source checkout step are shown, then only the checkout step, still for a new Terminal window, once uv appears, then the waiting folder opens by itself once `metab` does |
| `old-metab` | A stand-in reporting 0.12.0: the checkout step naming it and no server (the script checks); replacing it opens the folder by itself; a wrapper reporting 0.13.0 under the running server brings the restart offer, and Restart Servers reloads the window on a new port |
| `disk-image` | The copy on a read-only image of its own shows “Move Metabrowser to Applications”, naming the image |

Not covered: a translocated launch, which needs a quarantined copy that Gatekeeper
accepts and so a Developer ID build (`mb-e9fm`); its detection is tested on the path.

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
   checksummed, or if its `depends_on macos:` admits a macOS older than the app’s
   `LSMinimumSystemVersion`.

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
   read-only copy (App Translocation); it works, but belongs in Applications, and a
   launch notice says so ([The Launch Notice](#the-launch-notice)).
4. **Runtime.** The app runs the `metab` command-line tool and does not install it.
   Without one, or with one older than 0.12.1, the first launch shows the commands still
   missing ([The First Run Without metab](#the-first-run-without-metab)) and continues
   by itself once `metab` is installed.
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
| `Sources/ShellCore/Setup/` | The `metab` version the app requires, the first-run steps without one, fingerprints and watches of the files that decide the runtime, the offer to restart servers after an upgrade, and the launch notice for a disk-image or translocated copy. |
| `Sources/ShellCore/{Logs,Folders,Web}/` | Server logs, folder identity and window titles, files opened inside folders, tab placement, the saved session and its restore order, protected locations, the navigation policy, the web view configuration, the tab discard policy, and downloads. |
| `Sources/Metabrowser/` | The AppKit app: lifecycle, menus, folder sessions, windows, and the SwiftUI status and settings views. |
| `Tests/ShellCoreTests/` | Swift Testing tests of everything in `ShellCore`, with fake processes and fake machines, plus the real `posix_spawn` path with `/bin/sh` children and real `WKDownload`s from a local server. |
| `Resources/Info.plist` | The bundle’s property list. |
| `AppIcon/`, `scripts/build-icon.sh`, `Resources/AppIcon*.icns` | The app icon’s SVG masters and renderer, and the icons they build: `AppIcon.icns` for official builds and `AppIcon-Dev.icns` for development builds. See [AppIcon/README.md](AppIcon/README.md). |
| `VERSION` | The app’s version, set nowhere else. |
| `scripts/build-app.sh`, `scripts/common.sh`, `scripts/test-scripts.sh` | The bundle script, the variants and helpers every script shares, and the tests of those helpers that `make test` runs. |
| `scripts/check-setup-flows.sh` | The manual checks of the first-run screens and the launch notice ([Checking the Setup Flows by Hand](#checking-the-setup-flows-by-hand)). |
| `scripts/release.sh`, `notarize.sh`, `make-dmg.sh`, `check-dmg.sh` | The release pipeline and its steps. |
| `packaging/metabrowser-app.rb.template` | The Homebrew cask, filled in by each release. |

`ShellCore` holds everything that can be tested without a window; it imports no AppKit.
It imports WebKit only for what its tests can run in a `WKWebView` without a window: the
web view’s configuration and downloads.
The app target is the platform behavior the brief exempts from the CLI parity rule:
finding a runtime before one exists, windows, menus, the Dock, and file events.

### A Folder’s Server

1. **Open.** File > Open, File > Open Recent, the Dock menu’s recents, a drop on the
   Dock icon or on a window, Open With, `open -a Metabrowser.app FOLDER`, and the last
   session’s restore all arrive at one session per folder.
   The folder’s canonical path keys it, so one root has one server, whatever number of
   windows and tabs show it.
   A file opens inside a folder (see
   [Files, Tabs, Recents, and the Last Session](#files-tabs-recents-and-the-last-session)).
2. **Spawn.** `ServerSupervisor` runs
   `metab ROOT --no-open --host 127.0.0.1 --port 8411` with `posix_spawn`: in its own
   process group (`POSIX_SPAWN_SETPGROUP`), with only the descriptors it is given
   (`POSIX_SPAWN_CLOEXEC_DEFAULT`), with default signal handling restored, and with the
   folder as its working directory, so `.env` lookup matches `metab .` in Terminal.
   Its stdout and stderr go to the server log and to an in-memory tail.
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
5. **Fail.** If the server exits, never announces itself, or never answers, the window
   shows the reason, the last lines of output, Retry, Reveal Logs, and Runtime Settings.
   Nothing restarts automatically.
   After Retry, each window returns to the page it showed, on the new port.
6. **Stop.** Closing a folder’s last window stops its server: SIGTERM to the process
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
`~/.local/bin` is the one in `HOME`, as uv reads it; a Finder launch’s `HOME` is the
account’s own. Setup saves the runtime and the absolute paths of `git` and `gh`; later
launches only check that the saved `metab` is still executable and is the file that was
validated ([The Version It Requires](#the-version-it-requires)), so they start no extra
process. If nothing usable is found, Settings shows the steps that are missing
([The First Run Without metab](#the-first-run-without-metab)) and every place it looked.
Settings also chooses another `metab` with an open panel, runs `metab --doctor`, and
reveals the logs folder.
The runtime chosen there or found by Find Again is what folders opened afterwards start,
and what an open folder starts at its next Retry or File > Restart Server; until then,
open folders keep their servers.
Every start asks for the runtime the app accepts at that moment (`FolderServer`): a
folder’s first start, a restored folder’s start when its turn or its tab comes, Retry,
Restart Server, and the restart after an upgrade.
While there is none, because a search found nothing or the runtime’s file changed and
its check has not answered, a start waits and its windows say so, a restart stops
nothing, and both go ahead once a runtime is accepted.
When Find Again and a choice overlap, the one started last wins: a search that finishes
after a newer choice changes nothing.
A Find Again that finds nothing leaves no runtime, so the next folder waits for one
instead of starting the `metab` that failed.

### The First Run Without metab

When a search finds no usable `metab`, Settings shows only the steps still missing, each
a command with a Copy button (`SetupGuide`, `Sources/ShellCore/Setup/SetupGuide.swift`):

| Found | Steps shown |
| --- | --- |
| No uv | Install uv with its official installer, `curl -LsSf https://astral.sh/uv/install.sh \| sh` (or `brew install uv` when Homebrew is installed), then the `metab` step below in a new Terminal window |
| uv, no `metab` | `uv tool install metabrowser` |
| A `metab` in uv’s tool directory that does not run | `uv tool install --reinstall metabrowser`, since a plain install reports it as installed and changes nothing |
| A `metab` older than the minimum | `uv tool install --upgrade 'metabrowser>=0.12.1'` |

Those are the steps once the minimum is on PyPI (`MetabRequirement.isReleased`). Until
then uv can install only an older release, so every case ends in one step instead:
`make install` at the root of the source checkout the app was built from, then Choose
metab… and its `.venv/bin/metab`, naming the older `metab` found, if any.
A step after uv’s says to run it in a new Terminal window while uv’s directory is not on
the login shell’s `PATH` from the search, since the window that ran the installer has
not read the `PATH` it added.

- **Finding uv:** where its installer puts it (`XDG_BIN_HOME`, `XDG_DATA_HOME/../bin`,
  or `~/.local/bin`), `/opt/homebrew/bin`, `/usr/local/bin`, then the login shell’s
  `PATH` from the search, so a file check suffices.
- **Where `metab` will appear:** `uv tool dir --bin`, asked of the first uv found that
  no other account can change (`ExecutableTrust`), with uv’s location variables passed
  through. Without one, or if it fails to answer (logged), uv’s documented default, which
  the screen names.
- **Which uv it runs:** the app runs a uv it found by itself only if every directory and
  link from `/` to the file, and the file, belong to this user or root, none is writable
  by its group or by every account, and no access control entry grants a right to change
  it. Each one refused is named on the screen and in the log with the reason; the steps
  still count it as installed, since the user’s Terminal is what runs it.
  A standard Homebrew prefix is writable by the `admin` group, so its uv is refused,
  which costs only the question: uv’s default directory is the answer a Finder launch
  gets.
- **Continuing by itself:** the app watches that directory, every place discovery looks
  without a shell, every candidate the last search tried (those on the login shell’s
  `PATH` among them), and every place uv may be, once a second and when the app becomes
  active. A file’s fingerprint includes its mode, so `chmod +x` alone is a change.
  When `metab` appears or changes, it searches again, adopts the result, and opens the
  folders that were waiting.
  When uv appears, the steps shrink to the ones left.
- **Terminal:** `~/.local/bin` is not on macOS’s default `PATH`. The app needs nothing
  there, but Terminal does, so the screen suggests `uv tool update-shell` unless the
  login shell’s `PATH` already has uv’s tool directory.

The app never runs an installer itself.
“Install for me” (`mb-34oi`) waits on the clean-account matrix (`mb-5fp7`).

### The Version It Requires

`MetabRequirement` (`Sources/ShellCore/Setup/MetabVersion.swift`) sets the oldest
`metab` the app runs: 0.12.1, the first release with `GET /api/identity`. 0.12.0, the
latest published release, lacks the route, and 0.12.1 is not published yet, so for now
only a source checkout’s `metab` meets it.
A development build of 0.12.1 (`0.12.1.dev214+8b0603f7`, which PEP 440 orders before
0.12.1) counts as 0.12.1, or no checkout would run.
Its number says only that it was built after 0.12.0: one built before the route reached
`main` runs too, and its windows keep the names derived from their paths.

- **Below the minimum,** discovery skips that `metab` and tries the next place.
  If none qualifies, the app starts no server: Settings shows the version found, the
  version needed, and, once the minimum is published,
  `uv tool install --upgrade 'metabrowser>=0.12.1'` to copy (before then, the source
  checkout step above), and folders wait.
  The command asks for a floor rather than an exact version, because uv keeps the
  requirement in the tool’s receipt and a later `uv tool upgrade` would never move past
  a pin. Choose metab… refuses an older `metab` the same way.
- **Noticing an upgrade.** The runtime records its executable’s fingerprint (device,
  inode, size, modification time, and mode) from just before `metab --version` ran.
  The app compares it with the file once a second and when the app becomes active, and
  checks before each folder it opens, and at launch before it restores the last session.
  A change counts once two looks agree, which debounces a file caught in the middle of
  an install without proving the installer is done: the check reads the file again, and
  a later change is a new one.
  From the first look that sees a change, no server starts from the old runtime until a
  check, a Find Again, or a choice validates one, whichever finishes it; a choice being
  validated is never overtaken by a check the app starts by itself.
  The check runs `metab --version` again.
  A version the app accepts replaces the old one, and if open folders run servers that
  the same `metab` started at another version, an alert offers to restart them; a folder
  whose server never started is not counted.
  The restart uses the runtime accepted when the alert is answered, and restarts nothing
  if a later change left none.
  Anything else leaves no runtime, and a search looks for another.
- **What it cannot prevent:** an upgrade run in Terminal rewrites the environment the
  running servers import from, before the app notices or the user agrees, so a server
  can load new code beside old until it restarts (the
  [setup flows brief](../../docs/project/research/research-2026-11-11-uv-and-macos-app-install.md),
  Where This Breaks). An upgrade that changes only a dependency leaves `metab` itself
  unchanged and goes unnoticed.

### The Launch Notice

A copy opened from its disk image runs from a read-only volume, and a quarantined copy
opened where it was downloaded runs from a randomized read-only mirror (App
Translocation). Neither can be replaced in place, and the first stops working when the
image is ejected. macOS has no API to detect either, so `LaunchLocation`
(`Sources/ShellCore/Setup/LaunchLocation.swift`) reads the bundle’s path and volume, as
Sparkle does: a path containing `/AppTranslocation/` is translocated, and otherwise a
volume that `statfs` reports read-only is a disk image.
`URLResourceKey.volumeIsReadOnlyKey` is not used, since it reports the sealed system
volume as writable.

At launch such a copy shows “Move Metabrowser to Applications”, which says why and how:
drag the app to Applications in Finder, then open it from there.
Show in Finder opens the Applications folder and, on a disk image, selects the app in
the image; for a translocated copy, whose path hides the original, it opens the
Applications folder only.
Continue goes on, and “Don’t remind me” stops the notice for that bundle identifier.
The app moves nothing itself.
A copy it made of a translocated app would keep its quarantine and be translocated again
unless the app removed the attribute, which is a decision for a person.

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
  Until then, and if the route fails, the window names the folder from its path as
  `metab` would (`FolderIdentity.localFolder`). `window.title` holds the plain text,
  which the Window menu, Mission Control, the Dock, and accessibility read.
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

### Files, Tabs, Recents, and the Last Session

- **A file opens in its folder.** `open -a Metabrowser.app FILE` and a file chosen in
  File > Open show the file’s page in the most specific open folder that contains it, or
  else in its own folder, as `metab FILE` serves the file’s folder (`OpenTarget`).
  Symbolic links are resolved first, as `metab` resolves them, so a link opens where it
  points. The page is the file’s view route, spelled as `metab` spells it
  (`PageAddress.view`); a live test checks the spelling against the route `metab --path`
  announces. `open -a` delivers a file although `Info.plist` declares only
  `public.folder` (checked on macOS 26.5), so Finder’s Open With and the Dock still
  offer the app for folders only.
  A file opened while its folder’s server is starting, has failed, or is restarting
  loads once the server is ready: a requested page outlasts the page the window showed
  before, through Retry, a discard, and a save (`NextPage`).

- **Tabs.** Every folder window shares one tabbing identifier, so Merge All Windows,
  Move Tab to New Window, and dragging a tab combine any folders.
  Settings > Open folders in places a newly opened folder: as a tab of the front folder
  window, in a window of its own, or, by default, as System Settings > Desktop & Dock >
  “Prefer tabs when opening documents” says (`FolderPlacement`). Windows a page opens
  (`target=_blank`, Command-click) are tabs of their window, as before.

- **Background tabs give up their pages.** Each window’s shown tab keeps its page; of
  the background tabs, the three shown most recently keep theirs too.
  Every other background tab gives up its web view, which ends its WebContent process,
  and reloads its page from the folder’s running server when it is shown
  (`TabDiscardPolicy`). The limit’s basis follows this list.

- **Recents are macOS’s.** Opening a folder registers it with
  `NSDocumentController.noteNewRecentDocumentURL`, and File > Open Recent lists
  `recentDocumentURLs` each time it opens; the Dock menu shows the same list.
  macOS keeps the membership, the order, and the length (System Settings > Desktop &
  Dock > Recent documents, apps, and servers), and Clear Menu empties it: the app keeps
  no list of its own. A file registers the folder it opened in.
  A scratch bundle that declares only `public.folder` showed, on macOS 26.5, that a
  folder is recorded and is still listed at the next launch.
  This is the platform exemption the server-topology brief records; recent roots kept in
  `metab`, with a route, are Phase 4 (`mb-a5ru`).

- **The last session comes back.** The app saves its folder windows, front window first,
  with each window’s tabs, shown tab, and frame and each tab’s folder and page, to
  `~/Library/Application Support/<bundle identifier>/session.json`, mode 0600 in a 0700
  folder, half a second after a window opens or closes, a tab is shown, or a page loads,
  and once more at quit, before the servers stop.
  A save writes a private temporary file beside the session and renames it over the old
  one (`SessionStore`), so a launch after a crash finds the previous session or the new
  one, never part of one.
  The next launch reads the file once, through one descriptor: a regular file, not a
  link or a pipe, of at most 1 MB however it changes meanwhile.
  It rebuilds at most the front 20 windows and 50 tabs, each window keeping the tab it
  shows (`RestoreBudget`, whose basis follows this list), and admits every saved root
  again before deciding anything about it (`RootAdmission`): the file may have been
  edited, and a folder on the path replaced or relinked.
  Only a root whose identity is certain warms in the background.
  The walk opens each component relative to the one before, with `O_NOFOLLOW`, so a
  folder replaced after it was opened cannot redirect the rest, and it never opens a
  protected location or anything inside one, compared without regard to case and in its
  Data-volume spelling too (`/System/Volumes/Data/Volumes` is `/Volumes`). The folder it
  reaches must be on the home folder’s volume, and the kernel’s name for it
  (`F_GETPATH`, which undoes case variants and firmlinks) must hold no protected
  location; that name is the root’s identity, so aliases of one folder share one server.
  A root that falls short (a link anywhere on its path, another volume, a protected
  spelling) waits for its tab under the spelling it was saved with, untouched, so
  selecting it serves what that path names then.
  A root spelled with `.`, `..`, or empty components is dropped unopened, and so is one
  whose folder is gone.
  The launch recreates the windows and tabs, and only each window’s shown tab loads its
  page. The servers start one at a time, each after the one before it is ready or has
  failed: the front tab’s first, then those of the tabs the other windows show, front to
  back, then the rest (`RestoreQueue`). A tab that is selected meanwhile starts next.
  Each background root is admitted again just before its server starts, and one that
  changed while the servers before it started waits for its tab instead.
  The server takes a path, so a process that changes the path between that last check
  and the server resolving it can still win; the deferral is the app’s own policy, and
  macOS enforces its privacy grants regardless.
  A folder in a protected location (Desktop, Documents, Downloads, iCloud Drive and
  other cloud storage, other apps’ data, anything under `/Volumes` or `/Network`, or a
  folder that holds one, such as the home folder) starts only when one of its tabs is
  selected, so a launch raises no privacy prompt for a folder nobody is looking at; the
  front tab is selected, so it starts (`ProtectedLocations`). A protected folder that is
  gone says so only when its tab is selected.
  Settings > “Reopen the last session’s folders when Metabrowser opens” turns the
  restore off; the session is still saved.
  A session file that cannot be read is logged and ignored, and the next save replaces
  it.

The discard limit’s basis, measured on macOS 26.5.2 with
`scripts/measure-web-views.swift` against this repository’s own server:

| Measure | Result |
| --- | --- |
| WebContent processes for N web views | N, one each |
| One view’s WebContent footprint, 8 s after loading | 120–143 MB on the folder page (4 views), 111–112 MB on a Markdown page (3 views); the server-topology brief measured 155–210 MB with real pages |
| A released view’s WebContent process | gone within 1 s |
| A view that never loaded | no WebContent process |
| A fresh view loading the page from the warm server, to `didFinish` | 155–489 ms in 9 of 10 loads, and one of 3.7 s; in a run started 5 s after the server, while it was likely still walking the tree, two of five took 3.6 and 17.9 s |

Three background pages hold at most about 0.6 GB at the brief’s upper figure.
The limit is a conservative default, not a measured optimum: showing a discarded tab
costs a reload of a few hundred milliseconds, and how often people return to a tab past
the third is unmeasured.
A discarded tab keeps only its page’s address: it comes back at the top of the page,
with no Back or Forward history and none of the page’s own state that its address does
not hold.

The restore budget’s basis, measured the same day by building windows that each hold a
never-loaded web view, as a restore builds them:

| Built | Main-thread time | Footprint added to the app |
| --- | --- | --- |
| 20 tabs in one window | 588 ms | 23 MB |
| 50 tabs in one window | 1.76 s | 55 MB |
| 100 tabs in one window | 4.47 s | 113 MB |
| 20 separate windows | 187 ms | 16 MB |

Each window’s shown tab then loads a page of 111–143 MB, and each distinct root starts a
server of about 65 MB (the server-topology brief).
Twenty windows and fifty tabs keep a launch under two seconds of building and under 3 GB
of pages at the measured upper figure: far past an everyday session, and a bound on an
edited or corrupted file.

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
| **`/healthz`** | Readiness polls the `/view/` entry page. | Layering item 1 |
| **Rootless runtime report** | `metab --version` validates; `--doctor` output is shown as text. | Layering item 2 |
| **Explicit tool paths** | `git` and `gh` are found by their directories on `PATH`. | Layering item 5 |
| **Privacy-safe I/O** | Usage descriptions are declared; a protected folder prompts in the app’s name with no in-app guidance. | Layering item 6; macOS Platform Rules |
| **Settings served by Metabrowser** | A native Settings window. | Layering item 7 |
| **App-managed runtime** | None: a CLI install is required. | Recommendation 5.2; Wrapping uv |
| **First real release** | The release pipeline has run only with an ad hoc signature; no Developer ID build has been notarized. | Recommendation 6 |
| **Updates** | None: `brew upgrade --cask`, no in-app update notice, and no Sparkle. A copy run from its disk image or translocated gets a launch notice, and moving it is left to the user in Finder. | Recommendation 6; Updates |
| **DMG window layout** | Finder places the two icons itself. A fixed layout needs a `.DS_Store` in the image, which Apple’s tools cannot write; Finder scripting needs a GUI session and an Automation grant, so it is not reproducible in CI. | Recommendation 6 |
| **Variant gaps in the app** | Both variants write server logs to `~/Library/Logs/Metabrowser/`, so they share a folder’s log if both serve it, and the menu items say “Metabrowser” in the dev build. | Not in the brief (`mb-9xl0`) |
| **WebKit measurement gate** | Not run. Large-content bounds were measured in Chrome; `window.print()` and drag and drop are not yet checked by hand. | Recommendation 4 (`mb-etqi`) |
| **Multi-root and attach** | One server per root; no attaching to an agent’s server, no state files, no `metabrowser://` hand-off from the CLI. | Use Cases Under Exploration; Sharing an Installation |
| **Release CI** | `macos-app.yml` builds, tests, and rehearses the release with an ad hoc signature. No job signs and notarizes from secrets or drafts a release on a `macos-v*` tag, so a release is built by hand (`mb-e9fm`). | Next Steps |

## Known Limitations

- Finder’s Open With and the Dock icon accept folders only; a file opens through
  `open -a` or File > Open.
- The restore recreates windows, tabs, frames, and pages, but not full screen, Spaces,
  minimized windows, or each tab’s Back and Forward history.
  A discarded background tab loses the same within one launch: its history, its scroll
  position, and the page’s own state that its address does not hold.
- A restore past its budget, 20 windows and 50 tabs, rebuilds only the front ones.
  A page reached by the page’s own history changes, without a load, is saved at the next
  save or at quit.
- A restored folder’s server starts once the one before it answers, not once that one
  has finished walking its tree: `metab` reports no walk’s end, so the launch gate
  schedules starts, not crawls.
- The tab bar has no new-tab button: a new folder tab comes from File > Open with
  Settings set to tabs, or from Merge All Windows.
- Closing a folder’s last window stops its server, so reopening it starts a new one.
- A restarted server comes back on a new port, and local storage is per origin, as with
  the CLI.
- State-home variables (`XDG_CACHE_HOME`, `METABROWSER_CACHE_DIR`, and the rest) are not
  passed to the server, so the app always uses the default homes.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
