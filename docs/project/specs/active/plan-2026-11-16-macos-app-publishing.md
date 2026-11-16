# Plan for Publishing the macOS App

**Date:** 2026-11-16

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** In review.
Bead `mb-hl2i`, under the 0.13 release epic `mb-wzsl`, tracks this design; each
agent-implementable step below is a bead under it.
It details the open items of `mb-e9fm` (Developer ID signing, notarization, a DMG, and a
Homebrew cask) in the [native macOS app plan](plan-2026-11-10-native-macos-app.md).
Nothing here has been implemented, and no Developer ID build has been made.

## Overview

The owner asked, on 2026-11-16:

> “can we look at the [developer] setup for [a sibling app’s repository] and the
> corresponding github repo and help me design what needs to be set up for the apple
> application publishing to be equivalent.
> That repo also has some testing tools to check app signing for macOS and other details
> to make the app download and set up correctly.
> Let’s adapt to the parts that make sense, follow the best practices, and ensure
> they’re up to date (that repo is over a year old)”

The sibling is an Electron app by the same author, in a private repository, whose CI
builds signed disk images from a tag and is configured to notarize them.
This plan compares its setup with what `apps/macos` has, checks both against Apple’s and
GitHub’s current guidance, and lists what to build, what only the owner can do, and how
each step is verified.

Most of the pipeline already exists: `make macos-release` signs with the hardened
runtime, notarizes and staples the app and the image, and checks the image
([Building a Release](../../../apps/macos/README.md#building-a-release)). What is
missing is narrower:

- a signing setup that works on the build Mac, and a command that says what is wrong
  with it when it does not;
- checks that cover what Gatekeeper checks, on the build output and on the copy a user
  downloads, including quarantine and App Translocation;
- a release job that signs from a `macos-v*` tag with secrets no other job can reach;
- provenance a downloader can check: the checksum, GitHub’s asset digest, and an
  attestation;
- one written runbook for the owner’s part.

## Goals

- A downloaded DMG and the app in it pass every Gatekeeper check, with the notarization
  ticket stapled to both, so the first launch asks once and works offline.
- One read-only command reports whether a Mac can sign and notarize, and names the
  missing piece and the owner step that fixes it.
- The same checks run on the build output, on a draft release’s assets, and on the
  published assets, and each check fails the run rather than printing a warning.
- A release can be built on the owner’s Mac or by CI from a `macos-v*` tag, and both
  produce the same files and pass the same checks.
- Signing and notary secrets never appear in the repository, a command line, or a log,
  and only an approved release job on a release tag can read them.
- A downloader can check a download against the published SHA-256, GitHub’s digest, and
  a GitHub attestation.

## Non-Goals

- An installer package, and so a Developer ID Installer certificate: the app ships as a
  DMG, which a Developer ID Application identity signs
  ([Packaging Mac software for distribution](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution)).
- The Mac App Store and the App Sandbox (the
  [packaging brief](../../research/research-2026-11-08-macos-app-packaging.md) explains
  why neither fits).
- An in-app updater for the alpha.
  [Open Questions](#open-questions), Q4, recommends one path; the owner decides.
- An Intel or universal build: the app is arm64 and `ARCHES="arm64 x86_64"` already
  builds a universal one if wanted.
- A DMG window layout, which stays a gap in the app README for the reason it gives.
- Signing nested code for the app-managed runtime, which changes the entitlements
  question and belongs to that work (`mb-lrcd`).

## Background

### Current State

Verified on 2026-11-16 on the build Mac (macOS 26.5.2, Xcode 26.6, `notarytool` 1.1.2)
and in the repository at `main` commit `1dcbe93f1`:

| Piece | Where | State |
| --- | --- | --- |
| Build and sign | `apps/macos/scripts/build-app.sh` | Hardened runtime, secure timestamp, inside-out signing without `--deep`; refuses any entitlement (`require_no_entitlements` in `common.sh`) |
| Notarize and staple | `scripts/notarize.sh` | `notarytool submit --wait`, keychain profile or API key, saves the notary log, staples, runs `spctl`; does not read the log’s issues |
| Disk image | `scripts/make-dmg.sh` | UDZO image with the app, an Applications link, and the volume icon; signed; `.sha256` written |
| Image check | `scripts/check-dmg.sh` | Verifies, mounts read-only, checks contents, the app’s signature, the variant’s icon, tickets and `spctl` for a Developer ID build; reports quarantine; fails on any miss |
| Release | `scripts/release.sh`, `make macos-release` | Preflight (identity, notary credentials, icon, clean tree), then every step above, then the cask |
| Cask | `packaging/metabrowser-app.rb.template` | Rendered and checked; no tap repository exists |
| CI | `.github/workflows/macos-app.yml` | Tests, builds, rehearses the release ad hoc; no secrets; actions pinned by SHA |
| First-run checks | `scripts/check-setup-flows.sh` | Manual: no `metab`, an old `metab`, a launch from the image; a translocated launch is listed as not covered |

The build Mac cannot sign or notarize yet:

- `security find-identity -v -p codesigning` reports 0 valid identities.
  Without `-v` it lists one Developer ID Application identity.
  `openssl x509 -issuer` on its certificate shows the issuer
  `CN=Developer ID Certification Authority, OU=G2`, and the certificate is valid for
  more than a year. No keychain on the search list, nor the System keychain, holds a
  Developer ID intermediate; the system roots hold only the G1 one
  (`OU=Apple Certification Authority`, expiring 2027-02-01). So the chain cannot be
  built: the G2 intermediate is missing, which Apple DTS names as the usual cause
  ([forum thread 705473](https://developer.apple.com/forums/thread/705473)).
  `release.sh` checks `find-identity -v`, so it refuses the build.
- No `notarytool` keychain profile is stored.

On GitHub (read with `gh api`): the repository has no Actions secrets, one environment,
`pypi`, with no protection rules, no rulesets, immutable releases off, and the
repository’s “require actions pinned to a full-length commit SHA” policy off
(`devtools/check_supply_chain.py` enforces the pinning instead).
No `macos-v*` tag or release exists.

### The Sibling App’s Setup

Read from its repository and, read-only, its GitHub settings and releases:

- **Build and sign:** its packager signs with the hardened runtime and notarizes in one
  step. The certificate and its password are repository secrets, a base64 `.p12`, which
  the packager imports into a temporary keychain.
- **Notarization:** an Apple ID, an app-specific password, and a team ID, as repository
  secrets. The packager’s built-in step replaced an earlier custom notarization hook.
- **Entitlements:** one file applied to the app and every helper: JIT, unsigned
  executable memory, disabled library validation, Apple Events, camera, microphone,
  contacts, calendars, location, and photos.
  Gatekeeper assessment inside the packager is turned off.
- **Images:** separate arm64 and x64 DMGs, with no ZIP, no checksum file, and block maps
  for an updater.
- **CI:** one reusable workflow for every OS, run on every push, pull request, and tag,
  with the signing secrets inherited by every run, write permissions for the whole
  workflow, actions pinned by tag, a floating Node 20, and dependency installs that are
  not frozen. The macOS job’s logs have expired, so whether pull request builds signed
  and notarized is inferred from that configuration, not observed.
- **Releases:** a script bumps the version, commits, and tags; pushing the tag builds,
  and the packager uploads the assets to a draft release that the owner publishes.
  Its latest release is marked Latest with empty notes; its assets show no GitHub
  digest, which GitHub began computing at upload in June 2025, after they were uploaded.
- **Checks:** a DMG check script mounts the image, prints `codesign -dv` and
  `spctl -a -t exec` results with a pass or fail mark, and always exits 0. A helper
  decodes the download’s extended attributes: the quarantine flags, timestamp, and
  agent, and the where-from URLs.
  A canary icon is swapped for the production icon in CI, and end-to-end tests launch
  the built app.
- **Updates:** the updater points at an update server, but with no ZIP target the macOS
  build has nothing that server could deliver.
- **Setup:** the app can link its command-line tool into `/usr/local/bin`, asking for an
  administrator password when needed.

### What Is Out of Date or Weaker, and What Replaces It

| Sibling practice | Current practice |
| --- | --- |
| Notarizing with an Apple ID and app-specific password | An App Store Connect API key, which is not the owner’s Apple ID and can be revoked alone: a team key with an issuer, or, with Xcode 26, an individual key (`man notarytool`, Xcode 26.6); a keychain profile on a Mac, so no secret is typed |
| A broad entitlement file on every binary | No entitlements: page JavaScript runs in WebKit’s own WebContent process, and Apple says to use “only the entitlements that are absolutely necessary” ([Hardened Runtime](https://developer.apple.com/documentation/security/hardened-runtime)) |
| `spctl` as the check, which never fails the run | `syspolicy_check distribution` on macOS 14 and later, which Apple DTS prefers to `spctl` for apps; `spctl` still for the image; every check fails the run ([Testing a Notarised Product](https://developer.apple.com/forums/thread/130560)) |
| Repository secrets that every push and pull request build inherits | Environment secrets, released only to a job on a `macos-v*` tag after a required reviewer approves ([Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)) |
| Actions pinned by tag, write permission for the whole workflow | Full-SHA pins (already enforced here), least privilege per job, and optionally the repository’s SHA-pinning policy ([changelog](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)) |
| No checksum or attestation | A `.sha256` file (already here), GitHub’s asset digest ([changelog](https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/)), a build provenance attestation ([artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)), and an immutable release ([changelog](https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/)) |
| A release marked Latest with empty notes | A draft with notes, `--latest=false` so the Python package’s release stays Latest (already here) |

What is adopted, as practices: CI that signs and notarizes from a tag into a draft
release; a check that decodes the quarantine attribute of a real download; the canary
and production icon split (already stricter here, since `check-dmg.sh` refuses a mix);
and end-to-end checks of the built app.
What is not: the entitlements, the updater, and the command-line link, since the app
runs a `metab` the user installed and installs nothing.

### Current Apple and GitHub Practice

- **Developer ID certificates:** a Developer ID Application certificate signs the app
  and the DMG; a Developer ID Installer certificate signs only installer packages
  ([Packaging Mac software for distribution](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution)).
  Only the Account Holder creates or replaces them, choosing the “G2 Sub-CA”
  intermediary. A certificate whose issuer’s organizational unit is G2 needs no action
  ([replacing certificates](https://developer.apple.com/help/account/certificates/replace-developer-id-certificates)).
  The G2 intermediate, “Developer ID - G2”, expiring 2031-09-17, is on
  [Apple PKI](https://www.apple.com/certificateauthority/). The G1 intermediate expires
  2027-02-01: Mac software already signed and notarized with a secure timestamp keeps
  working, installer packages signed under it stop installing, and Apple’s account help
  says new G2 certificates are valid for one year
  ([notice of 2026-10-01](https://developer.apple.com/news/?id=w4atic4c),
  [replacing certificates](https://developer.apple.com/help/account/certificates/replace-developer-id-certificates)).
- **Hardened runtime and entitlements:** notarization requires the hardened runtime, a
  secure timestamp, a Developer ID signature on every executable, and no
  `get-task-allow`
  ([Notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)).
  Entitlements go on executables only, and the defaults are all false
  ([Hardened Runtime](https://developer.apple.com/documentation/security/hardened-runtime)).
  A WKWebView app needs no exception, since JIT runs in WebKit’s process, and a server
  it spawns is a separate process with its own signature; the app runs today with the
  hardened runtime and no entitlements (`build-app.sh`). A bundled, hardened Python
  would need `disable-library-validation` to load wheels signed by other teams (the
  [packaging brief](../../research/research-2026-11-08-macos-app-packaging.md),
  reproduced locally).
- **`notarytool`:** the notary service stopped accepting `altool` and Xcode 13 or
  earlier on 2023-11-01
  ([TN3147](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool)).
  `notarytool` takes an API key (`--key`, `--key-id`, and `--issuer` for a team key
  only; an issuer with an individual key returns 401), an Apple ID with an app-specific
  password, or a keychain profile that `store-credentials` validates before saving
  (`man notarytool`, Xcode 26.6). `notarytool history` tests credentials.
  Apple says to read the notary log even when a submission is accepted, that most
  submissions finish within 5 minutes and 98 percent within 15, and to stay under 75
  submissions a day
  ([Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow)).
  Apple’s documents do not name the API key role notarization needs; developers report
  that the Developer role works
  ([forum thread 133063](https://developer.apple.com/forums/thread/133063)), so that is
  unverified here.
- **Stapling:** a ticket can be stapled to an app, a DMG, or an installer package, not
  to a ZIP; without a stapled ticket, Gatekeeper may block a launch while the Mac is
  offline
  ([Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow)).
- **Signed DMG:** build the image from a folder populated with `ditto`, as a read-only
  zlib-compressed UDZO image, sign it with the Developer ID Application identity, a
  secure timestamp, and an identifier of its own, notarize it, and staple it.
  Apple says to notarize only the outermost container, since the service issues tickets
  for the nested app too, and to avoid heavily compressed images
  ([Packaging](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution),
  [Customizing](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow)).
  `release.sh` notarizes the app before packaging as well, so a copy dragged out of the
  image carries its own ticket; that is a second submission per release.
- **CI signing:** GitHub’s recipe creates a temporary keychain, imports the `.p12`, sets
  the key’s partition list so `codesign` can use it without a prompt, and puts the
  keychain on the search list; hosted runners are discarded after each job
  ([Sign Xcode applications](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications)).
  Its example imports with `-A`, which lets any application use the key; importing with
  `-T /usr/bin/codesign` is narrower.
  Environment secrets reach only jobs that name the environment, and only after a
  required reviewer approves; deployments can be limited to tags matching a pattern; and
  when self-review is prevented, the person who started a run cannot approve it, which a
  sole maintainer must leave off
  ([Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)).
- **Provenance:** `actions/attest` v4 writes a signed build provenance attestation for
  files (`id-token: write`, `attestations: write`), free for public repositories, and
  `gh attestation verify FILE -R OWNER/REPO` checks it
  ([actions/attest](https://github.com/actions/attest)). Immutable releases lock a
  published release’s assets and tag and give it a release attestation that
  `gh release verify` and `gh release verify-asset` check (gh 2.98.0). The setting is
  per repository and applies to every new release, the Python package’s included.
- **Updates:** Sparkle 2 verifies updates with EdDSA signatures from its appcast
  ([EdDSA](https://sparkle-project.org/documentation/eddsa-migration/)); its latest
  release is 2.10.1, and 2.9.5 and 2.9.6 fixed security issues
  ([releases](https://github.com/sparkle-project/Sparkle/releases)). Homebrew 5.0.0
  deprecated `--no-quarantine` and disabled official casks that fail Gatekeeper checks
  from September 2026 ([Homebrew 5.0.0](https://brew.sh/2025/11/12/homebrew-5.0.0)); it
  says nothing about third-party taps, but a quarantined download needs notarization
  anyway.
- **Verification tools:** `codesign --verify --deep --strict` first;
  `syspolicy_check distribution APP` on macOS 14 and later (on this Mac it prints “App
  passed all pre-distribution checks and is ready for distribution.”
  and exits 0 for a notarized third-party app); `spctl -a -t exec -vvv APP` and
  `spctl -a -t open -vvv --context context:primary-signature DMG`; and
  `codesign -vvvv -R="notarized" --check-notarization`
  ([Testing a Notarised Product](https://developer.apple.com/forums/thread/130560),
  updated 2024-12-05). `gktool scan` is a minimal Gatekeeper interface since macOS 14
  ([forum thread 706379](https://developer.apple.com/forums/thread/706379)). Apple DTS
  calls the full test a quarantined download on a fresh machine, ideally a VM restored
  from a snapshot, since Gatekeeper caches what it has seen, and says the quarantine
  attribute is not API.
- **App Translocation:** a quarantined app opened where it was downloaded runs from a
  randomized path; moving it first prevents that.
  Apple’s packaging guide says this happens on first launch and asks for a test of a
  later launch too; Apple DTS’s notes saw the path stay randomized on relaunch until the
  app was moved, and say there is no supported way to detect translocation
  ([Packaging](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution),
  [App Translocation Notes](https://developer.apple.com/forums/thread/724969)). Apple’s
  test matrix adds an upgrade over an older copy, a duplicate copy elsewhere, and a
  different account from the installer’s.

## Design

### Approach

Keep the existing scripts as the one implementation, used locally and in CI, and add
what the gap table names.
The job that holds signing secrets runs only Apple’s tools and pinned GitHub actions:
building and notarizing need Swift and Xcode, not the Python and npm environments, so no
third-party package code runs where the keys are.
Every check is a script that exits nonzero, so the same script gates a local release,
CI, and the owner’s acceptance of a download.

### Gap Table

| Item | Sibling | Metabrowser | Current practice | Proposal |
| --- | --- | --- | --- | --- |
| Developer ID Application identity | `.p12` in repository secrets | Present, not valid: G2 intermediate missing | G2-issued certificate; intermediate from Apple PKI | Owner installs the intermediate (O1); the doctor checks it (`mb-qu6j`) |
| Developer ID Installer identity | None | None | Installer packages only | Not needed |
| Hardened runtime, secure timestamp | Yes | Yes | Required | Keep; check the `runtime` flag and timestamp (`mb-4hwg`) |
| Entitlements | Broad, on every binary | None, enforced | Only what is needed | Keep none |
| Notary credentials | Apple ID and app-specific password | Scripts take a profile or API key; none stored | API key; keychain profile locally | Owner creates a key and profile (O2, O3) |
| Notary log | Not read | Saved, not read | Read every log | Fail on errors, print warnings (`mb-tfap`) |
| Stapling | The app, inferred from its configuration | App and DMG | Staple what is shipped | Keep |
| DMG | Packager’s target, two architectures | UDZO, signed, checksum, icon | UDZO, Developer ID, own identifier | Keep |
| Signing readiness | None | Preflight refuses, says little | n/a | A read-only doctor (`mb-qu6j`) |
| Image and app checks | Prints, exits 0 | Fails on misses | `syspolicy_check`, `spctl`, `stapler`, `--check-notarization` | Add the missing checks (`mb-4hwg`) |
| Quarantine and translocation | Decodes quarantine of a download | Reports quarantine; translocation untested | Quarantined download, fresh VM, later launch too | A release-download check (`mb-xd4o`) |
| CI release | Signs every push, pull request, tag | Ad hoc rehearsal only | Tag-only job, environment secrets | A release workflow (`mb-mww5`) |
| Ephemeral keychain | Packager’s | None | Temporary keychain, partition list | A keychain script, rehearsed on every change (`mb-3ey5`) |
| Workflow guard | None | SHA pins checked | n/a | Supply-chain rules for the release workflow (`mb-yqrs`) |
| Checksums and digests | None | `.sha256` | Digest shown by GitHub | Keep, and compare both (`mb-xd4o`) |
| Attestation | None | None | `actions/attest` | Attest the DMG (`mb-mww5`) |
| Immutable release | No | Off | Generally available | Owner decides (Q3) |
| Release notes, Latest | Empty, Latest | Draft, not Latest | n/a | Keep; notes in the runbook (`mb-63cx`) |
| Updates | Points at a server it cannot use | None; cask template | Cask now, Sparkle later | Recommend; owner decides (Q4) |
| Homebrew cask | None | Rendered and checked, never linted | `brew style` and `brew audit` | Lint it in CI (`mb-eoez`); owner creates the tap (O6) |
| Icons | Swapped in CI | Variants enforced | n/a | Keep |
| End-to-end launch | Tests launch the built app | Unit, live, and manual setup checks | Quarantined launch on a clean Mac | Covered by `mb-xd4o` |
| Architectures | arm64 and x64 | arm64 | n/a | Keep arm64 (Q6) |
| Command-line link | Links into `/usr/local/bin` | Installs nothing | n/a | Keep |

### Release Flow

Local, which works once O1 to O3 are done:

1. `make macos-signing-check` reports every piece ready.
2. `make macos-release SIGN_IDENTITY=… APPLE_KEYCHAIN_PROFILE=metabrowser-notary`
   builds, signs, notarizes and staples the app, packages, notarizes and staples the
   image, reads both notary logs, checks the image, and writes the checksum and cask.
3. The agent creates a draft release with the image and checksum, as the app README
   shows.
4. `make macos-check-release TAG=macos-vX.Y.Z` downloads the draft’s assets and checks
   them; the owner opens the downloaded image and approves the commit, digest, and
   notes; the release is published.

From CI, once O4 is done:

1. A `macos-v*` tag is pushed for a commit on `main` whose `VERSION` matches it.
2. **`sign`** waits for the owner’s approval of the `macos-release` environment, then
   checks out the tag, imports the identity and the pinned G2 intermediate into a
   temporary keychain with a random password generated in the job, writes the API key to
   a mode 0600 file, runs the signing doctor, runs `make macos-release`, deletes the
   keychain and the key (`always()`), and uploads the image and checksum.
   Permissions: `contents: read` only.
3. **`draft`** needs `sign`, holds no Apple secrets, attests the image, and creates the
   draft release with `--verify-tag --latest=false`. Permissions: `contents: write`,
   `id-token: write`, `attestations: write`.
4. The owner runs or watches `make macos-check-release` on the draft, then publishes.

`publish.yml` still runs its job only for `v` tags, so neither path reaches PyPI. Once
the release workflow exists, every pushed `macos-v*` tag starts it; for a release built
locally, the owner rejects its approval and the job ends without secrets.

### Components

- `apps/macos/scripts/check-signing.sh` and `make macos-signing-check`: new.
- `apps/macos/scripts/check-dmg.sh` and `notarize.sh`: extended.
- `apps/macos/scripts/check-release.sh` and `make macos-check-release`: new.
- `apps/macos/scripts/ci-keychain.sh`: new; used by both workflows.
- `.github/workflows/macos-release.yml`: new.
  `macos-app.yml`: rehearses the keychain script and lints the cask.
- `devtools/check_supply_chain.py` and its tests: rules for the release workflow.
- `apps/macos/README.md`, `docs/publishing.md`, `SUPPLY-CHAIN-SECURITY.md`: the runbook,
  the release checklist, and the review of each new action.

### API Changes

None. No route, model, or `metab` command changes; the scripts and Make targets are the
app’s internal release tooling.

## Implementation Plan

Each agent-implementable step is a bead under `mb-hl2i`:

| Bead | Step | Phase | Depends on |
| --- | --- | --- | --- |
| `mb-qu6j` | A read-only signing doctor | 1 | none |
| `mb-4hwg` | Gatekeeper checks in `check-dmg.sh` | 1 | none |
| `mb-tfap` | Read the notary log | 1 | none |
| `mb-xd4o` | Check a release as a downloader gets it | 1 | `mb-4hwg` |
| `mb-63cx` | The release runbook | 1 | `mb-qu6j`, `mb-4hwg`, `mb-tfap`, `mb-xd4o` |
| `mb-3ey5` | An ephemeral CI keychain script | 2 | none |
| `mb-mww5` | The release workflow | 2 | `mb-qu6j`, `mb-4hwg`, `mb-tfap`, `mb-3ey5` |
| `mb-yqrs` | Rules for the release workflow | 2 | `mb-mww5` |
| `mb-eoez` | Lint the generated cask in CI | 2 | none |

### Owner-Only Steps

**Owner only.** These use the owner’s Apple account, private keys, or repository
settings. The agent never types, stores, or prints a secret, and runs a step that uses
the Apple account (a notarization) only with the owner’s go-ahead.

- [ ] **O1. Install the G2 intermediate** “Developer ID - G2” from
  [Apple PKI](https://www.apple.com/certificateauthority/) into the login keychain, then
  confirm `security find-identity -v -p codesigning` lists one valid identity.
  Signing will ask for keychain access once; allow `codesign`.

- [ ] **O2. Create an App Store Connect API key** for notarization at
  https://appstoreconnect.apple.com/access/api: a team key with the Developer role,
  which developers report suffices (an individual key works with Xcode 26 and has no
  issuer). Download the `.p8` once.
  Accept any pending developer agreement first; `man notarytool` says the notary service
  serves developers who have accepted the relevant agreements.

- [ ] **O3. Store the notary profile** on the build Mac, then test it:

  ```shell
  xcrun notarytool store-credentials metabrowser-notary \
    --key AuthKey_KEYID.p8 --key-id KEYID --issuer ISSUER_UUID
  xcrun notarytool history --keychain-profile metabrowser-notary
  ```

- [ ] **O4. For CI signing (Q1):** export the identity as a `.p12` with a strong
  password; create the `macos-release` environment with the owner as required reviewer,
  self-review allowed, and deployments limited to tags matching `macos-v*`; add
  environment secrets, never repository secrets, for the base64 `.p12`, its password,
  the identity name, the `.p8` contents, the key ID, and the issuer ID.

- [ ] **O5. Repository settings (Q3):** optionally turn on immutable releases and the
  “require actions to be pinned to a full-length commit SHA” policy, and add a tag
  ruleset that stops `v*` and `macos-v*` tags being moved or deleted.

- [ ] **O6. Create the tap repository** if the cask ships (Q5).

- [ ] **O7. Approve each release:** the go-ahead for its notarizations, then the exact
  commit, the image’s SHA-256, and the notes; publish the draft.

- [ ] **O8. Open the downloaded image** in a browser download on a Mac or VM that has
  not run the app, answer Gatekeeper’s prompt, and launch once offline.

### Phase 1: Local Release Readiness

Everything here works without secrets, and makes the first release safe to build on the
owner’s Mac.

- [ ] **`mb-qu6j` A signing doctor.** `scripts/check-signing.sh`, run by
  `make macos-signing-check`, read-only: a valid Developer ID Application identity in
  the search list; its certificate’s issuer and whether that intermediate is present
  (naming “Developer ID - G2” and Apple PKI when it is not); days to expiry, failing
  under 30 and warning under 90; that `SIGN_IDENTITY`, when set, matches; Xcode and
  `notarytool` versions; the notary profile or API key variables, and with `ONLINE=1` a
  `notarytool history` call.
  Each miss names its owner step.
  `release.sh`’s preflight calls it.
- [ ] **`mb-4hwg` Gatekeeper checks in `check-dmg.sh`.** For a Developer ID build: the
  hardened runtime flag (`flags=…(runtime)` in `codesign -dvvv`), a secure timestamp,
  the Team ID matching `EXPECTED_TEAM_ID` when set, the full chain
  (`Developer ID Application`, `Developer ID Certification Authority`, `Apple Root CA`),
  `syspolicy_check distribution` on the app, and
  `codesign -R="notarized" --check-notarization` on the app and image beside the
  existing `stapler` and `spctl` checks; with `NOTARIZE=1` every one is required.
  Decode a quarantine attribute when present (flags, time, agent) instead of printing it
  raw.
- [ ] **`mb-tfap` Read the notary log.** After each submission `notarize.sh` reads the
  saved JSON with `plutil`, fails on any issue of severity `error`, prints each warning
  with its path, and prints the submission ID, status, and counts in one line for the
  release record.
- [ ] **`mb-xd4o` A release-download check.** `scripts/check-release.sh`, run by
  `make macos-check-release TAG=…`, for a draft or published release: downloads the
  image and checksum with `gh release download` into a scratch folder; checks
  `shasum -a 256 -c`, the asset digest from `gh release view --json assets`, and
  `gh attestation verify` (and `gh release verify-asset` once published, when immutable
  releases are on); applies a quarantine attribute if the download has none, labelled a
  simulation; runs `check-dmg.sh` with `NOTARIZE=1`. With `LAUNCH=1` it copies the app
  out of the image into a scratch Downloads folder, still quarantined, opens it, waits
  for the person at the Mac to answer Gatekeeper, checks that the process runs from an
  `/AppTranslocation/` path and shows the launch notice, quits, relaunches and records
  whether it is still translocated, then moves the app and checks a launch from the new
  place (measuring whether a move from Terminal clears translocation as a move in Finder
  does). The launch runs the unmodified release bundle, whose identity is the installed
  release’s, so the script refuses to run while a release copy is running, and backs up
  and restores that identity’s defaults and the shared `session.json`; on a VM or a
  separate account it needs neither.
- [ ] **`mb-63cx` The release runbook.** `apps/macos/README.md` Building a Release: the
  owner steps O1 to O8, the doctor, the checks, Apple’s test matrix (fresh, upgrade,
  duplicate, another account, moved and not moved), the notes template, and the approval
  record. `docs/publishing.md`: the app release in the checklist, with one rule for how a
  `macos-v*` tag is created (its tag section and the app README disagree today).
  `SUPPLY-CHAIN-SECURITY.md`: each new action’s review.

### Phase 2: Release From CI

- [ ] **`mb-3ey5` An ephemeral keychain script.** `scripts/ci-keychain.sh`, with
  `create`, `import`, and `cleanup` commands: a keychain in `RUNNER_TEMP` with a
  password generated in the job, imported with `-T /usr/bin/codesign` and a partition
  list of `apple-tool:,apple:,codesign:`, the G2 intermediate pinned by SHA-256 in the
  script, the keychain first on the user search list, and cleanup that deletes it and
  restores the list. `macos-app.yml` rehearses it on every change with a throwaway
  self-signed identity: the import succeeds, `security find-identity` lists the
  identity, and cleanup leaves nothing.
- [ ] **`mb-mww5` The release workflow.** `.github/workflows/macos-release.yml` as in
  [Release Flow](#release-flow): `push` of `macos-v*` tags only; refuses a tag that does
  not match `macos-v$(cat apps/macos/VERSION)` or a commit not on `main`; a full clone
  for the build number; `persist-credentials: false`; a timeout above two notarizations;
  actions pinned by full SHA and reviewed in `SUPPLY-CHAIN-SECURITY.md`; the notary logs
  kept as workflow artifacts, not release assets.
- [ ] **`mb-yqrs` Guard the release workflow.** `devtools/check_supply_chain.py` refuses
  a release workflow that runs on `pull_request`, `pull_request_target`, or
  `workflow_dispatch`, that grants `contents: write` to the job naming the signing
  environment, that names the environment in a job that installs the Python or npm
  locks, or that sets workflow-level write permissions; tests cover each rule.
- [ ] **`mb-eoez` Lint the cask in CI.** `macos-app.yml` runs `brew style` and
  `brew audit --cask` on the rendered rehearsal cask in a scratch tap, so a template
  change that Homebrew would reject fails before a release.

## Testing Strategy

| Step | How it is verified |
| --- | --- |
| O1 | `make macos-signing-check` reports the identity valid, the G2 intermediate present, and expiry over 90 days |
| O2, O3 | The doctor with `ONLINE=1` gets an answer from `notarytool history` |
| `mb-qu6j` | Today on the build Mac it must report exactly the missing G2 intermediate and the missing profile; `test-scripts.sh` feeds it recorded `security` and `openssl` output for valid, missing-intermediate, expiring, and mismatched identities |
| `mb-4hwg` | `test-scripts.sh` checks the new readers on copies of a system binary signed ad hoc with and without `--options runtime`; CI runs the extended `check-dmg.sh` on both images; the Developer ID branch is proven by the first signed build |
| `mb-tfap` | `test-scripts.sh` runs the log reader on fixture logs: accepted with no issues, accepted with a warning, and invalid with an error |
| `mb-xd4o` | Run on the first draft release before it is published, then on the published release; the launch part by the owner, on a VM or a second account if possible |
| `mb-3ey5` | The rehearsal in `macos-app.yml` passes, and a deliberate failure in import still leaves cleanup run |
| `mb-mww5` | The first `macos-v*` tag produces a draft whose image passes `make macos-check-release` and `gh attestation verify`; until then, `check_supply_chain.py` and a review of the workflow |
| `mb-yqrs` | Unit tests in `tests/` for each refused shape, and the real workflow passes |
| `mb-eoez` | The lint step passes on the rehearsal cask, and fails on a cask with a broken `url` in a test run |
| `mb-63cx` | `make format` and `make lint-check` (public hygiene included) pass; the owner follows the runbook for the first release |

## Rollout Plan

1. The owner does O1 to O3; the agent reruns the doctor.
2. Phase 1 lands as one stack; the first release, `macos-v0.1.0` as an alpha, is built
   on the owner’s Mac, checked from its draft, opened by the owner (O8), and published.
3. Phase 2 lands as a second stack; after O4 the next app release is the first from CI,
   checked from its draft with `make macos-check-release` like the first.

## Risks

- **A signing key in CI** can be stolen by a compromised action or workflow change.
  The environment approval, the tag-only trigger, SHA pins, no package installs in the
  signing job, and deleting the keychain at once bound it; signing only on the owner’s
  Mac removes it (Q1). Notarization tickets can be revoked for versions signed by a
  stolen key
  ([Notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)).
- **Gatekeeper caches** what the build Mac has seen, so a local first-launch check can
  pass where a clean Mac would not; Apple DTS recommends a fresh VM for the real test.
- **A simulated quarantine attribute** may not match a browser download, since the
  attribute is not API; the owner’s browser download (O8) is the acceptance test.
- **The translocation check runs the real release identity**, whose defaults and saved
  session the owner may use; the script’s backup and refusal guard that, and a VM avoids
  it.
- **Immutable releases cannot be repaired.** A defective published image needs a new
  patch version, as on PyPI, and the setting covers the Python package’s releases too.
- **Two notarizations per release** double the wait and count against 75 a day; Apple’s
  simplest path notarizes the DMG only, and loses the dragged-out app’s own ticket (Q7).
- **The certificate term:** new G2 certificates last a year, so renewal becomes routine;
  the doctor warns 90 days ahead.
- **`syspolicy_check`** cannot diagnose every problem (Apple DTS), and the API key role
  for notarization is undocumented.
- **macOS runner images** may or may not carry the G2 intermediate; the keychain script
  imports its own, pinned by hash.

## Open Questions

- **Q1. Where to sign:** on the owner’s Mac only, or also in CI behind the environment?
  Recommendation: the owner’s Mac for 0.1.0, and CI from the next release once O4 is
  done.
- **Q2. Notary credential:** a team API key (recommended), an individual key, or an
  app-specific password?
- **Q3. Immutable releases:** turn them on for the repository, accepting that they cover
  the Python package’s releases too?
  Recommendation: yes, before 0.1.0 is published.
- **Q4. Updates for the alpha:** recommendation: the Homebrew cask in a personal tap
  plus the release page, and an in-app “update available” notice from the GitHub
  releases API next; Sparkle 2 (2.10.1 or later, EdDSA keys held by the owner) once app
  releases are frequent enough that a notice is a burden.
  Each becomes a bead once decided.
- **Q5. The cask:** create the tap and publish the cask with 0.1.0, or wait?
- **Q6. Architectures:** arm64 only, as now?
- **Q7. Notarize twice or once:** keep notarizing the app before packaging so a
  dragged-out copy launches offline, or notarize only the DMG, as Apple’s simplest path
  does?
- **Q8. The tag:** may the agent push the `macos-v*` tag after the owner approves the
  commit, or does the owner push it?

## References

- [Native macOS app plan](plan-2026-11-10-native-macos-app.md) and its bead `mb-e9fm`
- [macOS packaging brief](../../research/research-2026-11-08-macos-app-packaging.md)
- [apps/macos/README.md](../../../apps/macos/README.md), Building a Release and What a
  Downloader Experiences
- [Publishing](../../publishing.md) and
  [Supply-Chain Security](../../../SUPPLY-CHAIN-SECURITY.md)
- Apple:
  [Notarizing macOS software before distribution](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution),
  [Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow),
  [Packaging Mac software for distribution](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution),
  [Hardened Runtime](https://developer.apple.com/documentation/security/hardened-runtime),
  [TN3147](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool),
  [Developer ID Sub-CA notice](https://developer.apple.com/news/?id=w4atic4c),
  [Replacing Developer ID certificates](https://developer.apple.com/help/account/certificates/replace-developer-id-certificates),
  [Apple PKI](https://www.apple.com/certificateauthority/)
- Apple DTS:
  [Testing a Notarised Product](https://developer.apple.com/forums/thread/130560),
  [App Translocation Notes](https://developer.apple.com/forums/thread/724969),
  [Resolving Gatekeeper Problems](https://developer.apple.com/forums/thread/706379),
  [a missing intermediate](https://developer.apple.com/forums/thread/705473)
- GitHub:
  [Sign Xcode applications](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications),
  [Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments),
  [Artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations),
  [actions/attest](https://github.com/actions/attest),
  [immutable releases](https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/),
  [asset digests](https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/),
  [SHA-pinning policy](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)
- Updates: [Sparkle releases](https://github.com/sparkle-project/Sparkle/releases),
  [Sparkle EdDSA](https://sparkle-project.org/documentation/eddsa-migration/),
  [Homebrew 5.0.0](https://brew.sh/2025/11/12/homebrew-5.0.0),
  [Acceptable Casks](https://docs.brew.sh/Acceptable-Casks)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
