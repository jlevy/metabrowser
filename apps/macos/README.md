# Metabrowser for macOS

**Status:** Alpha preview, built from source.
[The installation guide](../../docs/installation.md) says what is released.

This folder is the native macOS app: an AppKit and `WKWebView` shell that finds a
command-line install of `metab` and runs one server per folder or GitHub repository it
opens. This README is for building, testing, and releasing it.
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
make macos-check-release TAG=macos-vX.Y.Z BUILT=local EXPECTED_TEAM_ID=TEAMID  # check a release as downloaded
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
| Settings | user defaults `io.github.jlevy.metabrowser.dev` | the same, for `io.github.jlevy.metabrowser` |
| URL schemes | each declared scheme with `-dev` (none yet) | as declared |
| DMG | `build/Metabrowser-Dev-<VERSION>-arm64.dmg` | `build/Metabrowser-<VERSION>-arm64.dmg` |

`scripts/build-app.sh` writes the variant and the commit into the bundle’s property list
(`MetabrowserBuildVariant` and `MetabrowserSourceCommit`, the commit’s full ID with
`-dirty` when `apps/macos` had uncommitted changes), and the app reads them
(`AppIdentity`). The release check compares the full ID with the tag’s, and the About
box shows it as a [short commit ID](../../docs/design-system.md#short-commit-ids).
A bundle without the release variant counts as a development build.

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
restore the same windows, and File > Open Recent lists the same folders in both, since
`metab` keeps that list.
Their settings stay apart by bundle identifier.
Two copies can run at once: each claims a folder’s log before its server writes there
(`ServerLogLease`), each save of the session replaces the whole file (`SessionStore`),
and nothing on disk names a server to stop, so no copy can stop another’s.

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

`AppContractTests` needs no `metab`: it reads `tests/golden/app-contract.txt`, which
records what `metab` answers each command the app runs, and requires the app’s own
builders to write those command lines and its own readers to read those answers.
[The App’s Contract with metab](../../docs/project/architecture/arch-app-contract.md)
describes the contract, `metab-contract.toml` here declares it, and a change to what the
app runs or reads starts there.

What the unit tests cannot reach, the platform behavior that AppKit, WebKit, and macOS
decide, is checked by hand against a built development app with the
[macOS app hand checks](../../docs/project/qa/qa-macos-app-hand-checks.md), including
`scripts/check-setup-flows.sh` for the first-run screens and the launch notice.

### Where to Look While It Runs

- **Server log:** `~/Library/Logs/Metabrowser/<folder>-<hash>.log`, for a development
  build and a release alike, mode 0600. It holds the server’s output, with the app’s
  lifecycle events interleaved: start command, pid, announced URL, readiness time, stop,
  and exit status. File > Reveal Server Log opens it, and Help > Reveal Logs Folder opens
  the folder. Help > Open Event Log opens `metab`’s own event log (`EventLogLocation`), a
  separate record of its requests and work that `metab` writes to its state directory;
  it opens in a window on the log’s own directory, not inside an open folder that holds
  it, and stays out of Open Recent.
  A second running copy, or a folder opened again while its last server is still
  stopping, writes a log named for its own process beside it (`ServerLogLease`).
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
  Menu the recent targets, which `metab` keeps for both.
  `make run` starts the app with `METABROWSER_RECORD_RECENT=0`, so what a development
  run opens stays out of that list; a copy that is already running keeps the setting it
  started with.

### The WebKit Gate

`make macos-webkit-gate` runs `webkit-gate/run.mjs`, whose header lists its cases and
options (`PAIRS=n` and `CASES=a,b` pass through), against Google Chrome; it needs a
logged-in session. `node webkit-gate/run.mjs --checks` scripts the print and drop checks
instead. Its method and its last results are in
[Measured in WebKit](../../docs/project/architecture/arch-macos-app.md#measured-in-webkit).

### Continuous Integration

`.github/workflows/macos-app.yml` runs on pushes to `main` and on every pull request
that changes a path its filters name: `apps/macos`, the root `Makefile`, the workflow,
`metab`’s half of handing the app a target, and the app contract’s golden.
It uses no secrets and signs only ad hoc.
It runs on one pinned runner image, with its Xcode selected explicitly, both named in
its matrix: the toolchain the app is built with, on the oldest macOS it supports.

1. `make install`, after setting up uv, Python, and Node as `ci.yml` does.
2. `make macos-test` with `METABROWSER_SHELL_TEST_METAB` set to that environment’s
   `metab`, so the live tests run against the server this checkout locks.
   The step fails unless `LiveMetabTests` ran and passed.
3. `make macos-app`.
4. `make macos-dmg` and `make macos-release NOTARIZE=0`, then `scripts/check-dmg.sh` on
   both images, the rehearsal’s also against this checkout’s version and commit.
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
`codesign`, `ditto`, `hdiutil`, `xcrun notarytool`, `xcrun stapler`, `spctl`, and
`syspolicy_check`, with `jq`, which macOS includes from macOS 15, to read the notary
logs.
This section is the release runbook: who does what, the owner’s setup, each release
in order, the checks, and what only a signing session can confirm.
[The publishing plan](../../docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md)
says why each step is there.

### Who Does What

Steps marked **(Owner)** use the owner’s Apple account, private keys, or repository
settings, and only the owner does them.
An agent never types, stores, or prints a secret.
It runs the rest: the signing doctor, the checks, the tag, the draft, and the
publication the owner approved.
It signs or notarizes only during a release the owner started by unlocking the release
keychain.
It never approves a deployment and never calls the pending-deployments endpoint
(`POST /repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments`): the owner
approves `macos-release` deployments only in the web UI.

### Owner Setup

Run the signing doctor first, `make macos-signing-check`. It only reads, never unlocks a
keychain or asks for anything, and each miss it reports names the step below that fixes
it; run it again after each step.
O1 to O3 and O5 come before the first release, O4 before the first release CI builds,
and O6 after the alpha’s first round of feedback.
The commands name the release keychain as `KEYCHAIN`, the default that
`release_keychain` in `scripts/common.sh` gives (`SIGN_KEYCHAIN` names another):

```shell
KEYCHAIN=~/Library/Keychains/metabrowser-release.keychain-db
```

- **O1. The release keychain (Owner).**
  1. Install Apple’s Developer ID G2 intermediate into the login keychain, from
     `apps/macos`, using the copy committed here, which came from Apple PKI
     ([Supply-Chain Security](../../SUPPLY-CHAIN-SECURITY.md#apple-developer-id-intermediate-november-17-2026)):
     `security import packaging/DeveloperIDG2CA.cer -k ~/Library/Keychains/login.keychain-db`.
     codesign builds an identity’s chain only from keychains on the search list.
  2. Create the release keychain, typing its password at the prompt, never with `-p`:
     `security create-keychain "$KEYCHAIN"`. It does not add the keychain to the user
     search list (macOS 26), so add it, keeping the keychains on it: the doctor prints
     the `security list-keychains -d user -s` command with them.
     Make it lock on sleep and when idle:
     `security set-keychain-settings -l -u -t 900 "$KEYCHAIN"`. The doctor requires an
     idle lock of at most `release_keychain_lock_seconds` (`scripts/signing-lib.sh`).
  3. Move the Developer ID Application identity into it: export it from the login
     keychain as a `.p12`, import it with `security import FILE.p12 -k "$KEYCHAIN" -x`,
     with neither `-A`, `-T`, nor `-f pkcs12` (which would skip `-x`), typing the `.p12`
     password in the dialog, and delete the identity from the login keychain.
  4. Keep the `.p12` offline, in storage the owner controls, never in the repository or
     a synced folder. Imported with `-x`, the key cannot be exported again, so the `.p12`
     is its only backup, and losing both means a new certificate.
  5. Optionally, remove `/usr/bin/security` from the private key’s access list in
     Keychain Access, which takes away the silent use the import gave it.
  6. Check: the doctor reports the identity valid in the release keychain and absent
     from the login keychain, the intermediate installed, and the certificate’s expiry.
     With the keychain unlocked,
     `security export -k "$KEYCHAIN" -t identities -f pkcs12 -P x -o /dev/null` must
     fail. Then lock it, as whenever no release is running:
     `security lock-keychain "$KEYCHAIN"`.

- **O2. An App Store Connect API key (Owner)** for notarization, under Users and Access,
  Integrations, in App Store Connect: a team key with the Developer role, which
  developers report suffices.
  Accept any pending developer agreement first.
  Its `.p8` can be downloaded only once.

- **O3. The notary profile (Owner),** stored in the release keychain and tested, after
  which the `.p8` is deleted, so the profile is the key’s only copy on the Mac:

  ```shell
  xcrun notarytool store-credentials metabrowser-notary \
    --key AuthKey_KEYID.p8 --key-id KEYID --issuer ISSUER_UUID --keychain "$KEYCHAIN"
  ```

  Check: with the keychain unlocked, `ONLINE=1 make macos-signing-check` gets an answer
  from `notarytool history`.

- **O4. CI signing, before the first release CI builds (Owner).** A second Developer ID
  Application certificate, from a signing request made outside the release keychain, and
  a second team API key, both for CI only, so each can be revoked alone.
  The `macos-release` environment, with the owner as its required reviewer, self-review
  allowed, “Allow administrators to bypass configured protection rules” off, and
  deployments limited to tags matching `macos-v*`. Environment secrets, never repository
  secrets, for the CI certificate’s base64 `.p12`, its password, its identity name, the
  CI key’s `.p8` contents, its key ID, and the issuer ID. Then the CI identity, the
  exported `.p12`, and the downloaded `.p8` are deleted from the Mac.
  The release workflow that uses them is
  [planned](../../docs/project/architecture/arch-macos-app.md#planned).

- **O5. Repository settings, before 0.1.0 is published (Owner):** immutable releases on;
  a tag ruleset that stops `v*` and `macos-v*` tags being moved or deleted; and,
  optionally, the policy that requires actions pinned to a full-length commit SHA.
  `make macos-check-release` refuses a published release that is not immutable.

- **O6. The tap and the cask (Owner),** after the alpha’s first round of feedback, not
  with 0.1.0: a personal tap repository, whose `Casks/` takes each release’s
  `build/metabrowser-app.rb`.

- **O9. Yearly renewal (Owner).** G2 certificates last one year.
  The doctor warns `expiry_warn_days` before expiry and fails at `expiry_fail_days`
  (`scripts/signing-lib.sh`). The Account Holder creates the next Developer ID
  Application certificate and imports it into the release keychain as in O1, with `-x`
  and its `.p12` kept offline, then deletes the old identity there: two valid identities
  with one name make codesign refuse the name.
  Once CI signs, the next CI certificate replaces O4’s secrets too.
  Neither is exported from the release keychain.

- **After a leak** of an API key or an identity: revoke the API key in App Store
  Connect, delete the environment secrets, ask Apple to revoke the affected certificate,
  the owner’s or CI’s, and the notarization tickets of what it signed
  ([Notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)),
  and replace what was revoked (O2 to O4, O9).

### Each Release

In this order. The owner’s approvals, O7, come at steps 1, 3, and 8, and O8 is step 7.
`V` is the version, `MAJOR.MINOR.PATCH`.

1. **The commit, O7 (Owner approves).** `echo "$V" > apps/macos/VERSION` in a reviewed
   pull request, landed on `main`, and that commit’s full SHA recorded as
   `RELEASE_COMMIT`. The owner approves that exact SHA. Before it, the `metab` release
   that `MetabRequirement.minimumRelease` names is published and verified on PyPI, and
   `RELEASE_COMMIT` contains the commit that sets `MetabRequirement.isReleased` to true
   (`Sources/ShellCore/Setup/MetabVersion.swift`): without it no downloader’s `metab`
   runs the app, and `make macos-release` refuses the build.

2. **The tag.** The agent creates `macos-v$V` on GitHub at `RELEASE_COMMIT`, as
   [macOS App Releases](../../docs/publishing.md#macos-app-releases) describes, never by
   pushing it from a clone.
   The tag is permanent from then on: a failure that needs a change is released under
   the next version, and a transient one is retried at the same tag
   ([Failure Handling](../../docs/publishing.md#failure-handling)).

3. **The go-ahead, O7 (Owner).** At the build Mac, at a checkout of `RELEASE_COMMIT`,
   the owner unlocks the release keychain, typing its password at the prompt:

   ```shell
   git switch --detach "$RELEASE_COMMIT"
   security unlock-keychain "$KEYCHAIN"
   ```

4. **The build:**

   ```shell
   make macos-release SIGN_IDENTITY="Developer ID Application: Name (TEAMID)" \
     APPLE_KEYCHAIN_PROFILE=metabrowser-notary
   security lock-keychain "$KEYCHAIN"
   ```

   macOS asks for the key twice, once when `build-app.sh` signs the app and once when
   `make-dmg.sh` signs the image.
   The dialog names the key, not the file: answer **Allow**, never **Always Allow**,
   which would trust codesign with the key for good, and deny a third request.
   The app’s notarization wait can outlast the keychain’s idle lock; if it does, signing
   and submitting the image first ask to unlock the keychain again.
   Lock it when the build ends, whether it passed or not.
   `scripts/release.sh` stops at the first failure of these steps:
   1. **Preflight:** the signing doctor, `scripts/check-signing.sh --for-release`, finds
      a valid identity in the release keychain, the intermediate, and the notary
      profile, and finds the keychain unlocked; the published icon exists, and
      `apps/macos` has no uncommitted changes.
   2. **App:** `build-app.sh` builds and signs it, with the identity from the release
      keychain alone, the hardened runtime, and a secure timestamp, inside out and never
      with `--deep`, and refuses any entitlement and any signature whose entitlements
      `codesign` cannot read.
   3. **App notarization:** `notarize.sh` runs `syspolicy_check notary-submission` on
      the app, which stops a rejection before it is submitted, zips the app with
      `ditto`, submits it with `notarytool submit --wait`, and saves the notary log as
      `build/release/notary-Metabrowser.app.json`. It reads the log: an issue of
      severity error fails, each warning is printed with its path, and a
      `notary record:` line gives the submission ID, the status, and the counts.
      It staples the ticket to the app and runs `spctl --assess --type execute`. A
      stapled app opens without reaching Apple, also after it is dragged out of the
      image.
   4. **Image:** `make-dmg.sh` stages the app, an `Applications` link, and the app’s
      icon as `.VolumeIcon.icns`, creates a read-write image to set the volume’s
      custom-icon flag, converts it to a compressed UDZO image, signs it, and writes its
      checksum.
   5. **Image notarization:** the app inside the image is checked again, and the image
      is submitted, its log read, and it is stapled and assessed with
      `spctl --assess --type open`, and its checksum is written again, since stapling
      changes it.
   6. **Check:** `check-dmg.sh` checks the image as a downloader meets it
      ([The Checks](#the-checks)).
   7. **Cask:** `build/metabrowser-app.rb`, the cask template in `packaging/` with the
      version, the checksum, and the image’s architecture filled in: `-arm64.dmg`
      declares `depends_on arch: :arm64`, `-x86_64.dmg` declares `:x86_64`, and
      `-universal.dmg` (`ARCHES="arm64 x86_64"`) declares none.
      The release stops if the cask’s URL would name another image than the one
      checksummed, or if its `depends_on macos:` admits a macOS older than the app’s
      `LSMinimumSystemVersion`.

   It ends by naming the release’s assets, `release_assets` in `scripts/common.sh`.
   `NOTARY_TIMEOUT` bounds the wait for a verdict; `scripts/notarize.sh` documents it
   and its default. `make macos-notarize FILE=build/Metabrowser-<VERSION>-arm64.dmg`
   retries one step, and `make macos-release NOTARIZE=0` rehearses every step without
   credentials.

5. **The draft.** The agent attaches the image and its checksum to a draft on the tag,
   not the Latest release, with the notes ([Release Notes](#release-notes)):

   ```shell
   gh release create "macos-v$V" --draft --verify-tag --latest=false \
     --title "Metabrowser for macOS $V" --notes-file NOTES.md \
     "apps/macos/build/Metabrowser-$V-arm64.dmg" \
     "apps/macos/build/Metabrowser-$V-arm64.dmg.sha256"
   ```

6. **The download check.** From the checkout of `RELEASE_COMMIT`, whose icons
   `check-dmg.sh` compares the image’s with, the agent runs the check, and the owner
   then runs it with `LAUNCH=1` at the Mac, on a VM or a second account if one is at
   hand:

   ```shell
   make macos-check-release TAG="macos-v$V" BUILT=local EXPECTED_TEAM_ID=TEAMID
   make macos-check-release TAG="macos-v$V" BUILT=local EXPECTED_TEAM_ID=TEAMID LAUNCH=1
   ```

   Each output goes into the approval record.
   `EXPECTED_TEAM_ID` is required: without an attestation, the Team ID is what ties the
   image to the owner. `LAUNCH=1` exits nonzero on a miss, and an answer of no is one; it
   takes `y` or `yes` and `n` or `no`, and asks again on anything else.
   If a `LAUNCH=1` run is interrupted, the release identity’s defaults, session, and
   recent documents stay cleared and its backup in `apps/macos/build/launch-check-TIME`
   is their only copy: the next run, and `make macos-clean`, refuse until
   `scripts/launch-release.sh --restore build/launch-check-TIME`, run in `apps/macos`,
   puts them back. Quit Metabrowser first: the restore refuses while any copy runs, since
   a running copy saves its session over the restored one.

7. **O8, the owner’s download (Owner).** On a Mac or VM that has not run the app, the
   owner downloads the draft’s image in a browser, opens it, answers Gatekeeper’s
   prompt, and launches the app once offline.

8. **Approval and publication, O7 (Owner approves).** The owner approves the image’s
   SHA-256 and the notes.
   The agent publishes the draft without making it the Latest release, which stays the
   Python package’s, then checks it again as published:

   ```shell
   gh release edit "macos-v$V" --draft=false --latest=false
   make macos-check-release TAG="macos-v$V" BUILT=local EXPECTED_TEAM_ID=TEAMID
   ```

   The second check also verifies the immutable release’s attestation and that the
   release is not Latest.
   In the web UI, untick “Set as the latest release” before publishing.

The build’s outputs:

| File | What it is |
| --- | --- |
| `build/release/Metabrowser.app` | The signed, notarized, and stapled app |
| `build/Metabrowser-<VERSION>-arm64.dmg` | The image to publish |
| `build/Metabrowser-<VERSION>-arm64.dmg.sha256` | One `shasum -a 256` line |
| `build/metabrowser-app.rb` | The cask |
| `build/notary-*.json`, `build/release/notary-*.json` | The notary logs, each beside the file it is for |

0.1.0 ships without a cask: the tap and the cask follow the alpha’s first round of
feedback (O6). Publishing the release does not publish to PyPI: `publish.yml` runs its
job only for a `v` tag, the Python package’s. No workflow builds, signs, or drafts the
release yet; that job is
[planned](../../docs/project/architecture/arch-macos-app.md#planned).
What a downloader of a signed release meets, from Gatekeeper’s first check to the
privacy prompts, is in [the user guide](../../docs/macos-app.md).

### The Checks

Every check exits nonzero on a miss, so the same script gates a local release, CI, and
the owner’s acceptance of a download.
Each script’s header lists what it checks.

| Script | What it checks | Where it runs |
| --- | --- | --- |
| `scripts/check-signing.sh` (`make macos-signing-check`) | The release keychain, the identity, its expiry and issuer, the G2 intermediate, Xcode and notarytool, and the notary credentials; read-only | The build Mac, and each release’s preflight; macOS CI against a throwaway keychain |
| `scripts/notarize.sh` | `syspolicy_check notary-submission` before each submission, and the notary log after it | Each submission |
| `scripts/check-dmg.sh` | The image and its contents, the icons, the hardened runtime, and for a Developer ID build the secure timestamp, the Team ID, the chain, the stapled tickets, `spctl`, `syspolicy_check distribution`, and `codesign --check-notarization` | Every image built; macOS CI on both its images; the download check |
| `scripts/check-release.sh` (`make macos-check-release`) | A draft or published release as downloaded: the checksum, GitHub’s digest, the build provenance `BUILT` names, immutable releases on for a draft, and the immutable release and Latest once published, `check-dmg.sh` with `NOTARIZE=1` and `EXPECTED_TEAM_ID`, and that the app is the release variant, the tag’s version, and built from the tag’s commit; it quarantines a download that has none, for `LAUNCH=1` | Step 6 and step 8 of each release |
| `scripts/launch-release.sh` (`LAUNCH=1`) | The first launch, which must be translocated, the relaunch and a move from Terminal, recorded, and a move in Finder, after which it must not be; the person’s confirmations | At the Mac only, never in CI |

`scripts/test-release-logic.sh` runs what these scripts decide on stand-ins for Apple’s
tools, in `make test` on Linux and in `make macos-test`.

### The Test Matrix

Before each release is published, on a Mac or VM that has not run the app, or a second
account, since Gatekeeper caches what it has seen:

- **Fresh:** O8, and the download check with `LAUNCH=1`.
- **Not moved and moved:** `LAUNCH=1` records the translocated first launch, the
  relaunch, a move from Terminal, and a move in Finder.
- **A duplicate:** with a copy in Applications, a second copy opened from elsewhere runs
  and shows the launch notice; the record says which copy opened.
- **Another account** than the one that installed the app opens it from Applications.
- **An upgrade** over the previous release’s copy in Applications, from the second
  release on: the app opens with its settings and recent folders.

The other macOS releases, standard accounts, and Macs without the Command Line Tools are
the clean-account matrix of the
[native app plan](../../docs/project/specs/active/plan-2026-11-10-native-macos-app.md#phase-5-setup-runtime-and-updates),
which this one does not repeat.

### Release Notes

The notes follow [Release Notes](../../docs/publishing.md#release-notes), from this
template:

````markdown
An alpha preview of Metabrowser for macOS, the native app for browsing folders with
Metabrowser. It runs your own installation of `metab`; [the installation
guide](https://github.com/jlevy/metabrowser/blob/main/docs/installation.md) says which
macOS and which `metab` it needs.

## Changes

- One line per user-visible change, compatibility note, or important fix.

## Verify the Download

```shell
shasum -a 256 -c Metabrowser-X.Y.Z-arm64.dmg.sha256
gh release verify-asset macos-vX.Y.Z Metabrowser-X.Y.Z-arm64.dmg --repo jlevy/metabrowser
```

**Full changes:** https://github.com/jlevy/metabrowser/compare/macos-vPREVIOUS...macos-vX.Y.Z
````

The first release has no previous tag, so its notes link the tag’s tree instead.

### The Approval Record

Each release keeps a record, in its tracking issue, of:

- `RELEASE_COMMIT`, and who approved it and when;
- the tag’s SHA as `gh api` reported it after creating it;
- the doctor’s report from the preflight, and both `notary record:` lines;
- the image’s SHA-256, and who approved it and the notes, and when;
- the download check’s output on the draft and on the published release, and the launch
  record `LAUNCH=1` prints;
- O8’s result: the Mac or VM, its macOS version, and the offline launch;
- the results of the signing-session checks below.

### Checks Only a Signing Session Can Make

This repository’s tests run on Linux and on macOS CI, which have no Developer ID, no
notary account, and no person to answer a prompt.
These are confirmed only at the build Mac, the first time and again when Xcode or macOS
changes, and each result goes in the approval record:

1. The doctor, run before O1 to O3, reports exactly the missing release keychain, the
   missing G2 intermediate, and the missing notary profile, and shows no prompt.
2. With the release keychain locked, the doctor still finds its identity and shows no
   prompt; whether it can read the lock settings and the profile while locked is noted.
3. The doctor finds the profile `notarytool store-credentials` saved.
   It looks for the keychain item notarytool 1.1 uses, which Apple does not document: if
   it reports the profile absent while `ONLINE=1` succeeds, the item’s name has changed.
4. O1’s export check fails, so the key cannot be exported.
5. The release asks for the key exactly twice.
6. `syspolicy_check notary-submission` passes on the app and on the app in the image.
7. Both notary logs are fetched and read: two `notary record:` lines, Accepted, with any
   warnings listed.
8. `check-dmg.sh` with `NOTARIZE=1` passes on the signed image: the hardened runtime, a
   secure timestamp, the Team ID, the chain, the tickets, `spctl`,
   `syspolicy_check distribution`, and `codesign --check-notarization` on the app and on
   the image, a use of it that Apple DTS gives only for other code.
9. The download check passes on the draft with `BUILT=local`, and again once published.
10. `LAUNCH=1`: the first launch is translocated and shows the launch notice; whether
    the relaunch stays translocated; whether a move from Terminal ends it; and that a
    move in Finder does.
11. After `LAUNCH=1` on an account with the release identity’s own state, its defaults,
    session, and recent documents are as they were.
    The run does not back up or clear the identity’s WebKit data, caches, or saved
    window state, or the server logs.
12. O8 agrees with the download check’s simulated quarantine: a browser download is
    quarantined, and Gatekeeper asks once.
    The simulation matters only to `LAUNCH=1`; none of `check-dmg.sh`’s tools judges a
    file differently for its quarantine.

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
| `Sources/ShellCore/`, `Sources/ShellViews/`, `Sources/Metabrowser/` | The decisions testable without a window, the web view and its container and the chooser’s menu item, and the AppKit app |
| `Tests/ShellCoreTests/` | Swift Testing tests of `ShellCore`, with fake processes and machines, plus real `posix_spawn` children and real `WKDownload`s from a local server |
| `Resources/Info.plist` | The bundle’s property list |
| `AppIcon/`, `scripts/build-icon.sh`, `Resources/AppIcon*.icns` | The icon’s SVG masters and renderer, and the icons they build ([AppIcon/README.md](AppIcon/README.md)) |
| `VERSION` | The app’s version, set nowhere else |
| `scripts/build-app.sh`, `scripts/common.sh`, `scripts/test-scripts.sh` | The bundle script, the variants and helpers every script shares, and the tests of those helpers |
| `scripts/release.sh`, `notarize.sh`, `make-dmg.sh`, `check-dmg.sh` | The release pipeline and its steps |
| `scripts/check-signing.sh`, `signing-lib.sh`, `keychain-status.swift` | The signing doctor, its checks, and its read-only keychain reader |
| `scripts/notary-lib.sh` | What `notarize.sh` decides: credentials, the check before a submission, and reading the notary log |
| `scripts/gatekeeper-lib.sh` | What `check-dmg.sh` reads from a signature and a quarantine attribute |
| `scripts/check-release.sh`, `check-release-lib.sh`, `launch-release.sh`, `quarantine.swift` | The download check, its decisions, the launch check, and the helper that quarantines a download as a browser does |
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
