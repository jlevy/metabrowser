# Metabrowser for macOS

**Status:** Alpha preview, built from source.
[The installation guide](../../docs/installation.md) says what is released.

This folder is the native macOS app: an AppKit and `WKWebView` shell that finds a
command-line install of `metab` and runs one server per folder it opens.
This README is for building, testing, and releasing it.
[Using the app](../../docs/macos-app.md) is the user guide, and
[the app’s architecture](../../docs/project/architecture/arch-macos-app.md) describes
how it works.

## Build, Test, and Run

You need a Mac on the macOS release that `Package.swift` declares in `platforms`, with
an Xcode whose Swift meets its `swift-tools-version`, and a `metab` the app accepts:
`MetabRequirement.minimumRelease` in `Sources/ShellCore/Setup/MetabVersion.swift` is the
oldest. While `MetabRequirement.isReleased` is false, only a source checkout’s `metab`
meets it: `make install` at the repository root builds `.venv/bin/metab`, and Settings >
Choose metab… points the app at it (so does `open --env METABROWSER_METAB=…`). Once the
floor is published, a CLI install does, as
[the installation guide](../../docs/installation.md) describes.

From the repository root (each target delegates to `apps/macos/Makefile`, whose header
documents it, and prints a skip message on systems other than macOS):

```shell
make macos-test                      # unit tests (swift test), the scripts' and the gate's checks
make macos-app                       # build, assemble, and sign build/dev/Metabrowser.app
make macos-run FOLDER="$HOME/notes"  # build the app and open a folder with it
make macos-dmg                       # build/Metabrowser-Dev-<VERSION>-arm64.dmg, checked
make macos-release                   # the official build; see Building a Release
make macos-notarize FILE=path        # notarize and staple one .app or .dmg
make macos-signing-check             # the signing doctor: can this Mac sign a release? Read-only
make macos-build                     # debug build only
make macos-clean                     # remove .build and build
make macos-webkit-gate               # the WebKit measurement gate; needs Google Chrome
```

`make verify` neither needs nor runs Swift, so Linux CI is unchanged; the app has its
own [macOS workflow](#continuous-integration).
What the release scripts decide does not need Apple’s tools, so `make test` checks that
on Linux as well (see [Testing](#testing)).

`scripts/build-app.sh` builds a release binary, strips it, lays out the bundle, stamps
the variant’s identity and the version, copies the variant’s icon, and signs.
It signs ad hoc by default, which runs on this Mac only.
Set `SIGN_IDENTITY="Developer ID Application: Name (TEAMID)"` to sign with the hardened
runtime and a secure timestamp.
Any identity it names, of whatever kind, is looked for only in the release keychain,
`SIGN_KEYCHAIN` (by default `release_keychain` in `scripts/common.sh`). Its header
documents `BUILD`, `ARCHES`, `ICON`, and `SIGN_KEYCHAIN`.

### Versions

`VERSION` holds the version, `MAJOR.MINOR.PATCH`, and nothing overrides it; a release is
tagged `macos-v<VERSION>`. `CFBundleVersion` is the commit count of `HEAD`, so a shallow
clone is refused unless `BUILD` is set.
The app versions separately from the Python package, which it runs but does not contain.

### Variants

Every build is one of two variants, and the variant decides the bundle’s identity.
Both are named Metabrowser:

|  | dev | release |
| --- | --- | --- |
| Bundle | `build/dev/Metabrowser.app` | `build/release/Metabrowser.app` |
| Bundle identifier | `io.github.jlevy.metabrowser.dev` | `io.github.jlevy.metabrowser` |
| Icon | `Resources/AppIcon-Dev.icns`, the canary icon with a gold rim | `Resources/AppIcon.icns`, the published icon |
| About box | “Development build · VERSION (BUILD) · COMMIT” | “Release · VERSION (BUILD) · COMMIT” |
| Server logs | `~/Library/Logs/Metabrowser/` | the same folder |
| App data (the saved session) | `~/Library/Application Support/Metabrowser/` | the same folder |
| Settings and recent folders | user defaults `io.github.jlevy.metabrowser.dev`, and macOS’s recent documents for that identifier | the same, for `io.github.jlevy.metabrowser` |
| URL schemes | each declared scheme with `-dev` (none yet) | as declared |
| DMG | `build/Metabrowser-Dev-<VERSION>-arm64.dmg` | `build/Metabrowser-<VERSION>-arm64.dmg` |

`scripts/build-app.sh` writes the variant and the commit into the bundle’s property list
(`MetabrowserBuildVariant` and `MetabrowserSourceCommit`, the commit with `-dirty` when
`apps/macos` had uncommitted changes), and the app reads them (`AppIdentity`). A bundle
without the release variant counts as a development build.

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

One name has a cost: both bundles are `Metabrowser.app`, so they cannot both sit in
`/Applications` under that name.
A development build normally runs from `build/dev/`, and the canary icon in the Dock and
the About box’s first line tell it from an installed release.
Both keep their files in folders named for the app, so they write one logs folder and
restore the same windows, while their settings and recent folders stay apart by bundle
identifier. Two copies can run at once: each claims a folder’s log before its server
writes there (`ServerLogLease`), each save of the session replaces the whole file
(`SessionStore`), and nothing on disk names a server to stop, so no copy can stop
another’s.

`scripts/build-icon.sh` regenerates both icons from the masters in `AppIcon/`; see
[AppIcon/README.md](AppIcon/README.md).

### Testing

`make macos-test` runs `make test` in `apps/macos`: it builds the WebKit gate’s driver,
which no product ships, so a change to the views or configuration it shares with the app
cannot break it unnoticed; runs the Swift suites in three processes, since the WebKit
suites and the exit stress suite each stall the main actor that every suite shares (the
Makefile says which); runs `scripts/test-scripts.sh`; and runs the gate’s Node tests
(`webkit-gate/*.test.mjs`), which need no browser.
`scripts/test-scripts.sh` runs `scripts/test-release-logic.sh`, which checks what the
release scripts decide on stand-ins for Apple’s tools and runs in the repository’s
`make test` too, and, on a CI runner only, the signing doctor against a throwaway
keychain. A bare `swift test` runs every suite in one process.

To run the tests against a real server too:

```shell
METABROWSER_SHELL_TEST_METAB="$PWD/.venv/bin/metab" make macos-test  # at the repository root
```

The live tests check that `metab` against the version the app requires.

What the unit tests cannot reach, the platform behavior that AppKit, WebKit, and macOS
decide, is checked by hand against a built development app with the
[macOS app hand checks](../../docs/project/qa/qa-macos-app-hand-checks.md), including
`scripts/check-setup-flows.sh` for the first-run screens and the launch notice.

### Where to Look While It Runs

- **Server log:** `~/Library/Logs/Metabrowser/<folder>-<hash>.log`, for a development
  build and a release alike, mode 0600. It holds the server’s output, with the app’s
  lifecycle events interleaved: start command, pid, announced URL, readiness time, stop,
  and exit status. File > Reveal Server Log opens it, and Help > Reveal Logs Folder opens
  the folder. A second running copy, or a folder opened again while its last server is
  still stopping, writes a log named for its own process beside it (`ServerLogLease`).
- **App log:** `log stream --predicate 'subsystem == "io.github.jlevy.metabrowser.dev"'`
  for a development build; the subsystem is the bundle identifier, so a release build
  logs as `io.github.jlevy.metabrowser`.
- **Web Inspector:** Safari’s Develop menu, in debug builds or after
  `defaults write io.github.jlevy.metabrowser.dev WebInspectorEnabled -bool true`.
- **Start over:** `defaults delete io.github.jlevy.metabrowser.dev` forgets the saved
  runtime and the window preferences, so the next launch runs discovery again.
  Each variant has its own defaults domain, named by its bundle identifier.
  Deleting `~/Library/Application Support/Metabrowser/session.json` forgets the last
  session, a release’s too, since both variants share it, and File > Open Recent > Clear
  Menu the recent folders, which macOS keeps for each bundle identifier.

### The WebKit Gate

`make macos-webkit-gate` runs `webkit-gate/run.mjs`, whose header lists its cases and
options (`PAIRS=n` and `CASES=a,b` pass through), against Google Chrome; it needs a
logged-in session. `node webkit-gate/run.mjs --checks` scripts the print and drop checks
instead. Its method and its last results are in
[Measured in WebKit](../../docs/project/architecture/arch-macos-app.md#measured-in-webkit).

### Continuous Integration

`.github/workflows/macos-app.yml` runs on pushes to `main` and on every pull request
that changes `apps/macos`, the root `Makefile`, or the workflow.
It uses no secrets and signs only ad hoc.
It runs on one pinned runner image, with its Xcode selected explicitly, both named in
its matrix: the toolchain the app is built with, on the oldest macOS it supports.

1. `make install`, after setting up uv, Python, and Node as `ci.yml` does.
2. `make macos-test` with `METABROWSER_SHELL_TEST_METAB` set to that environment’s
   `metab`, so the live tests run against the server this checkout locks.
   The step fails unless `LiveMetabTests` ran and passed.
3. `make macos-app`.
4. `make macos-dmg` and `make macos-release NOTARIZE=0`, then `scripts/check-dmg.sh` on
   both images.
5. The development app, zipped with `ditto`, and the development image, uploaded as
   artifacts kept for the workflow’s `retention-days`. The rehearsal’s image carries the
   published icon on an ad hoc signature, so it is checked and never uploaded.
   Like any ad hoc build, a downloaded artifact runs only after Open Anyway (see
   [Ad Hoc Builds](#ad-hoc-builds)).

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
`codesign`, `ditto`, `hdiutil`, `xcrun notarytool`, `xcrun stapler`, and `spctl`.

### Once per Mac

Start with the signing doctor, `make macos-signing-check`, which only reads: it says
what this Mac lacks and names the owner step in the
[publishing plan](../../docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md#owner-only-steps)
that fixes it.
Those steps keep the identity and the notary profile in a release keychain
(`release_keychain` in `scripts/common.sh`, or `SIGN_KEYCHAIN`) that stays locked except
during a release; signing and notarizing use only that keychain.
The plan’s release runbook replaces this section.

1. **A Developer ID Application certificate**, with its private key, in the release
   keychain, and the Developer ID G2 intermediate it chains through
   (`packaging/DeveloperIDG2CA.cer`) on the search list.
   It needs the Apple Developer Program, and only the account holder can create one.

2. **Notary credentials in the release keychain**, saved once under a profile name, so
   no secret appears in a command line or an environment:

   ```shell
   xcrun notarytool store-credentials metabrowser-notary \
     --key AuthKey_KEYID.p8 --key-id KEYID --issuer ISSUER_UUID \
     --keychain ~/Library/Keychains/metabrowser-release.keychain-db
   ```

   That is an App Store Connect API key; `--apple-id`, `--team-id`, and an app-specific
   password work too.

3. **The published icon**, `Resources/AppIcon.icns`, committed.

### Each Release

Set the new version, `V`, with `echo "$V" > apps/macos/VERSION` in a reviewed pull
request, land it on `main`, and record that commit’s full SHA as `RELEASE_COMMIT`. After
the owner approves it, create the `macos-v$V` tag on GitHub at that SHA as
[macOS App Releases](../../docs/publishing.md#macos-app-releases) describes, never by
pushing it from a clone.
Then the owner unlocks the release keychain, the go-ahead for the release, and builds
the approved commit:

```shell
V=MAJOR.MINOR.PATCH
git switch --detach "$RELEASE_COMMIT"
security unlock-keychain ~/Library/Keychains/metabrowser-release.keychain-db
make macos-release SIGN_IDENTITY="Developer ID Application: Name (TEAMID)" \
  APPLE_KEYCHAIN_PROFILE=metabrowser-notary
security lock-keychain ~/Library/Keychains/metabrowser-release.keychain-db
```

The tag is permanent from then on: a failure that needs a change is released under the
next version, and a transient one is retried at the same tag
([Failure Handling](../../docs/publishing.md#failure-handling)).

`scripts/release.sh` then runs, stopping at the first failure:

1. **Preflight:** the signing doctor, `scripts/check-signing.sh --for-release`, finds a
   valid identity in the release keychain, the intermediate, and the notary profile, and
   finds the keychain unlocked; the notary credentials are set, the published icon
   exists, and `apps/macos` has no uncommitted changes.
2. **App:** `build-app.sh` builds and signs it, with the identity from the release
   keychain alone, the hardened runtime, and a secure timestamp, inside out and never
   with `--deep`, and refuses any entitlement and any signature whose entitlements
   `codesign` cannot read.
3. **App notarization:** `notarize.sh` runs `syspolicy_check notary-submission` on the
   app, which stops a rejection before it is submitted, zips the app with `ditto`,
   submits it with `notarytool submit --wait`, and saves the notary log as
   `build/release/notary-Metabrowser.app.json`. It reads the log: an issue of severity
   error fails, each warning is printed with its path, and a `notary record:` line gives
   the submission ID, the status, and the counts.
   It staples the ticket to the app and runs `spctl --assess --type execute`. A stapled
   app opens without reaching Apple, also after it is dragged out of the image.
4. **Image:** `make-dmg.sh` stages the app, an `Applications` link, and the app’s icon
   as `.VolumeIcon.icns`, creates a read-write image to set the volume’s custom-icon
   flag, converts it to a compressed UDZO image, signs it, and writes its checksum.
5. **Image notarization:** the app inside the image is checked again, and the image is
   submitted, its log read, and it is stapled and assessed with
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

The outputs:

| File | What it is |
| --- | --- |
| `build/release/Metabrowser.app` | The signed, notarized, and stapled app |
| `build/Metabrowser-<VERSION>-arm64.dmg` | The image to publish |
| `build/Metabrowser-<VERSION>-arm64.dmg.sha256` | One `shasum -a 256` line |
| `build/metabrowser-app.rb` | The cask |
| `build/notary-*.json`, `build/release/notary-*.json` | The notary logs, each beside the file it is for |

`NOTARY_TIMEOUT` bounds the wait for a verdict; `scripts/notarize.sh` documents it and
its default.
`make macos-notarize FILE=build/Metabrowser-<VERSION>-arm64.dmg` retries one
step, and `make macos-release NOTARIZE=0` rehearses every step without credentials.

To publish, attach the image and its checksum to a draft release on the tag:

```shell
gh release create "macos-v$V" --draft --verify-tag --latest=false \
  --title "Metabrowser for macOS $V" \
  "apps/macos/build/Metabrowser-$V-arm64.dmg" \
  "apps/macos/build/Metabrowser-$V-arm64.dmg.sha256"
```

Before publishing, the owner opens the draft’s image from a browser download on a Mac
that has not run the app, and approves the image’s SHA-256 and the notes (O8 and O7 in
the
[publishing plan’s owner steps](../../docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md#owner-only-steps)).
Then publish it without making it the repository’s Latest release, which stays the
Python package’s:

```shell
gh release edit "macos-v$V" --draft=false --latest=false
```

0.1.0 ships without a cask (the plan’s Q5): the tap and the cask follow the alpha’s
first round of feedback, when a release copies `build/metabrowser-app.rb` to `Casks/` in
a personal tap. Publishing the release does not publish to PyPI: `publish.yml` runs its
job only for a `v` tag, the Python package’s. No workflow builds, signs, or drafts the
release yet; that job is
[planned](../../docs/project/architecture/arch-macos-app.md#planned).

What a downloader of a signed release meets, from Gatekeeper’s first check to the
privacy prompts, is in [the user guide](../../docs/macos-app.md).

### Ad Hoc Builds

A development or rehearsal DMG is signed ad hoc.
It runs on the Mac that built it, but on any Mac that downloads it, CI artifacts
included, Gatekeeper refuses it as unverifiable, and since macOS 15 only Open Anyway, in
the Privacy & Security pane of System Settings, overrides that.
Do not hand one out as a release.

## Source Layout

`Package.swift` is SwiftPM only, with no Xcode project.
[The architecture](../../docs/project/architecture/arch-macos-app.md#modules) maps
`Sources/`.

| Path | Holds |
| --- | --- |
| `Sources/ShellCore/`, `Sources/ShellViews/`, `Sources/Metabrowser/` | The decisions testable without a window, the web view and its container, and the AppKit app |
| `Tests/ShellCoreTests/` | Swift Testing tests of `ShellCore`, with fake processes and machines, plus real `posix_spawn` children and real `WKDownload`s from a local server |
| `Resources/Info.plist` | The bundle’s property list |
| `AppIcon/`, `scripts/build-icon.sh`, `Resources/AppIcon*.icns` | The icon’s SVG masters and renderer, and the icons they build ([AppIcon/README.md](AppIcon/README.md)) |
| `VERSION` | The app’s version, set nowhere else |
| `scripts/build-app.sh`, `scripts/common.sh`, `scripts/test-scripts.sh` | The bundle script, the variants and helpers every script shares, and the tests of those helpers |
| `scripts/release.sh`, `notarize.sh`, `make-dmg.sh`, `check-dmg.sh` | The release pipeline and its steps |
| `scripts/check-signing.sh`, `signing-lib.sh`, `keychain-status.swift` | The signing doctor, its checks, and its read-only keychain reader |
| `scripts/notary-lib.sh` | What `notarize.sh` decides: credentials, the check before a submission, and reading the notary log |
| `scripts/test-release-logic.sh`, `scripts/fixtures/` | The release scripts’ decisions on stand-ins for Apple’s tools, which Linux CI runs too, and their inputs |
| `scripts/check-setup-flows.sh`, `scripts/setup-check/` | The hand checks of the first-run screens and the launch notice, and their stand-ins |
| `scripts/measure-web-views.swift` | The measurement behind `TabDiscardPolicy` |
| `webkit-gate/` | The WebKit measurement gate: `run.mjs`, the in-page `probe.js`, `summary.mjs` for its verdicts, `processes.mjs` and `static-server.mjs`, and `driver/`, the `WebKitDriver` target |
| `packaging/metabrowser-app.rb.template` | The Homebrew cask, filled in by each release |
| `packaging/DeveloperIDG2CA.cer` | Apple’s Developer ID G2 intermediate, reviewed in [Supply-Chain Security](../../SUPPLY-CHAIN-SECURITY.md#apple-developer-id-intermediate-november-17-2026) |

`make lint-check` at the repository root lints `webkit-gate/` with Biome and type-checks
it strictly (`webkit-gate/tsconfig.json`, and `probe.js` under the root
`tsconfig.json`).

## Coding Guidelines

The app follows tbd’s language-neutral guidelines (tbd has no Swift guideline): general
coding and comment rules, error handling, testing and TDD, filesystem rules, release
engineering, supply-chain hardening, and backward compatibility.
Decision logic lives in `ShellCore` with tests, and the app target only connects it to
AppKit and WebKit. What is left as it is, on purpose:

- **Errors ignored with a reason.** Each remaining `try?` names why at its line.
- **Errors only logged, with a reason.** A lifecycle event that cannot be appended to a
  server log is in the unified log already.
- **Layout numbers in views.** SwiftUI paddings and spacings stay inline, as SwiftUI
  code reads; numbers that set behavior (timeouts, limits, window and zoom sizes) are
  named and say why.
- **Regression tests name their defect.** A test written for a review finding says what
  the code used to do, since that defect is why the test exists.
- **Dispatch handlers for other queues are `@Sendable`.** Under main-actor default
  isolation, a closure written in a main-actor context is inferred main-actor, and Swift
  6’s runtime check traps when it runs on another queue
  (`AppDelegate.installTerminationSignals` has the case that found it).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
