# Plan for Publishing the macOS App

**Date:** 2026-11-16

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** In review.
Bead `mb-hl2i`, under the 0.13 release epic `mb-wzsl`, tracks this design; each
agent-implementable step below is a bead under it.
It details the open items of `mb-e9fm` (Developer ID signing, notarization, a DMG, and a
Homebrew cask) in the [native macOS app plan](plan-2026-11-10-native-macos-app.md).
The owner answered Q1, Q2, Q3, and Q5 on 2026-11-16; Q4, Q6, Q7, and Q8 are open
([Open Questions](#open-questions)). Nothing here has been implemented, and no Developer
ID build has been made.

## Overview

The owner asked, on 2026-11-16:

> “can we look at the [developer] setup for [the sister app’s repository] and the
> corresponding github repo and help me design what needs to be set up for the apple
> application publishing to be equivalent.
> That repo also has some testing tools to check app signing for macOS and other details
> to make the app download and set up correctly.
> Let’s adapt to the parts that make sense, follow the best practices, and ensure
> they’re up to date (that repo is over a year old)”

The sister app is the one the
[native macOS app plan](plan-2026-11-10-native-macos-app.md) describes, by the same
author and in a private repository.
jlevy/metabrowser#341 already adapted its build, signing, and download pipeline for
`apps/macos` (`mb-nnhs`), so this plan covers what remains.
It compares the two setups’ practices, checks both against Apple’s and GitHub’s current
guidance, and lists what to build, what only the owner can do, and how each step is
verified. It records practices, not that repository’s configuration.

Most of the pipeline already exists: `make macos-release` signs with the hardened
runtime, notarizes and staples the app and the image, and checks the image
([Building a Release](../../../apps/macos/README.md#building-a-release)). What is
missing is narrower:

- a signing setup that works on the build Mac, keeps the identity locked except during a
  release the owner started, and has a command that says what is wrong with it;
- checks that cover what Gatekeeper checks, on the build output and on the copy a user
  downloads, including quarantine and App Translocation;
- a release job that signs from a `macos-v*` tag with secrets no other job can reach;
- provenance a downloader can check: the checksum, GitHub’s asset digest, the immutable
  release’s attestation, and, for a CI build, a build provenance attestation;
- one written runbook for the owner’s part.

## Goals

- A downloaded DMG and the app in it pass every Gatekeeper check, with the notarization
  ticket stapled to both, so the first launch asks once and works offline.
- One read-only command reports whether a Mac can sign and notarize and whether its
  release keychain is locked, and names the missing piece and the owner step that fixes
  it.
- The same checks run on the build output, on a draft release’s assets, and on the
  published assets, and each check fails the run rather than printing a warning.
- A release can be built on the owner’s Mac or by CI from a `macos-v*` tag.
  Both produce the same files and pass the same Gatekeeper and download checks, and the
  download check says which provenance it verified.
- Nothing signs or notarizes outside a release the owner started: on the owner’s Mac the
  identity and the notary profile live in a keychain that is otherwise locked, and in CI
  only the owner, in the web UI, releases the secrets to a job on a release tag.
- Signing and notary secrets never appear in the repository or a log.
  On the owner’s Mac, passwords are typed at a prompt, never passed as arguments.
  On the ephemeral CI runner they reach `security` only as arguments, with shell tracing
  off, in a job that runs nothing else.
- A downloader can check a download against the published SHA-256 and GitHub’s digest, a
  published release against its immutable-release attestation, and a CI-built image
  against its build provenance attestation.

## Non-Goals

- An installer package, and so a Developer ID Installer certificate: the app ships as a
  DMG, which a Developer ID Application identity signs
  ([Packaging Mac software for distribution](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution)).
- The Mac App Store and the App Sandbox (the
  [packaging brief](../../research/research-2026-11-08-macos-app-packaging.md) explains
  why neither fits).
- An in-app updater for the alpha.
  [Open Questions](#open-questions), Q4, recommends one path, and `mb-fl72` tracks it.
- A release ZIP and manifest beside the DMG (`mb-5jr9`), from which `metab` would
  install the app (`mb-92d9`). The native plan schedules both after the setup flows
  pass, so 0.1.0 ships the DMG and its checksum.
  The asset names come from one place ([Release Flow](#release-flow)), so `mb-5jr9` adds
  the ZIP and manifest there once.
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
| Disk image | `scripts/make-dmg.sh` | UDZO image at zlib level 9 with the app, an Applications link, and the volume icon; signed; `.sha256` written |
| Image check | `scripts/check-dmg.sh` | Verifies, mounts read-only, checks contents, the app’s signature, the variant’s icon, tickets and `spctl` for a Developer ID build; reports quarantine; fails on any miss |
| Release | `scripts/release.sh`, `make macos-release` | Preflight (identity, notary credentials, icon, clean tree), then every step above, then the cask |
| Cask | `packaging/metabrowser-app.rb.template` | Rendered and checked; no tap repository exists |
| CI | `.github/workflows/macos-app.yml` | Tests, builds, rehearses the release ad hoc; no secrets; actions pinned by SHA |
| First-run checks | `scripts/check-setup-flows.sh` | Manual: no `metab`, an old `metab`, a launch from the image; a translocated launch is listed as not covered |

The build Mac cannot sign or notarize yet:

- `security find-identity -v -p codesigning` reports 0 valid identities.
  Without `-v` it lists one Developer ID Application identity, in the login keychain.
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

### Practices Compared

Adopted from the sister app, as practices: CI that signs and notarizes from a tag into a
draft release; a check that decodes the quarantine attribute of a real download; the
canary and production icon split (already stricter here, since `check-dmg.sh` refuses a
mix); and launches of the built app, here in CI (`mb-epgm`) and as the release’s manual
check (`mb-u36j`). Not adopted: entitlements, an updater, and a command-line link, since
the app runs a `metab` the user installed and installs nothing.

For each topic compared, this plan follows current practice:

| Topic | Current practice |
| --- | --- |
| Notary credential | An App Store Connect API key, which is not the owner’s Apple ID and can be revoked alone: a team key with an issuer, or, with Xcode 26, an individual key (`man notarytool`, Xcode 26.6); a keychain profile on a Mac, so no secret is typed |
| Entitlements | None: page JavaScript runs in WebKit’s own WebContent process, and Apple says to use “only the entitlements that are absolutely necessary” ([Hardened Runtime](https://developer.apple.com/documentation/security/hardened-runtime)) |
| Checks | `syspolicy_check distribution` on macOS 14 and later, which Apple DTS prefers to `spctl` for apps; `spctl` for the image; every check fails the run ([Testing a Notarised Product](https://developer.apple.com/forums/thread/130560)) |
| CI secrets | Environment secrets, released only to a job on a `macos-v*` tag after a required reviewer approves ([Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)) |
| Actions and permissions | Full-SHA pins (already enforced here), least privilege per job, and optionally the repository’s SHA-pinning policy ([changelog](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)) |
| Provenance | A `.sha256` file (already here), GitHub’s asset digest ([changelog](https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/)), a build provenance attestation ([artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)), and an immutable release ([changelog](https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/)) |
| Release notes | A draft with notes, `--latest=false` so the Python package’s release stays Latest (already here) |

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
- **Keychains:** `codesign --keychain FILE` looks for the signing identity only in that
  keychain, but builds the certificate chain from the user’s search list
  (`man codesign`). `notarytool` reads and stores a profile in a keychain file given by
  `--keychain`, and asks to unlock it when it is locked (`man notarytool`).
  `security create-keychain` and `security unlock-keychain` prompt for the password when
  `-p` is not given, and `security import` asks for a `.p12` password in a dialog when
  `-P` is not given; `security set-keychain-settings -l -u -t SECONDS` locks a keychain
  on sleep and after that many seconds idle (`man security`).
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
- **`notarytool`:** the notary service stopped accepting `altool` on 2023-11-01
  ([TN3147](https://developer.apple.com/documentation/technotes/tn3147-migrating-to-the-latest-notarization-tool)).
  `notarytool` takes an API key (`--key`, `--key-id`, and `--issuer` for a team key
  only; an issuer with an individual key returns 401), an Apple ID with an app-specific
  password, or a keychain profile that `store-credentials` validates before saving
  (`man notarytool`, Xcode 26.6). An API key’s private key can be downloaded only once
  (`man notarytool`). `notarytool history` tests credentials.
  Apple says to read the notary log even when a submission is accepted, that most
  submissions finish within 5 minutes and 98 percent within 15, and to stay under 75
  submissions a day
  ([Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow)).
  `syspolicy_check notary-submission` “Runs the same checks on an app as the Apple
  notary service” (`man syspolicy_check`), so it catches a rejection before a
  submission. Apple’s documents do not name the API key role notarization needs;
  developers report that the Developer role works
  ([forum thread 133063](https://developer.apple.com/forums/thread/133063)), so that is
  unverified here.
- **Stapling:** a ticket can be stapled to an app, a DMG, or an installer package, not
  to a ZIP, so an app shipped in a ZIP carries a ticket only if the app itself was
  stapled first; without a stapled ticket, Gatekeeper may block a launch while the Mac
  is offline
  ([Customizing the notarization workflow](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow)).
- **Signed DMG:** build the image from a folder populated with `ditto`, as a read-only
  zlib-compressed UDZO image, sign it with the Developer ID Application identity, a
  secure timestamp, and an identifier of its own, notarize it, and staple it.
  Apple says to notarize only the outermost container, since the service issues tickets
  for the nested app too, and to avoid heavily compressed images
  ([Packaging](https://developer.apple.com/documentation/xcode/packaging-mac-software-for-distribution),
  [Customizing](https://developer.apple.com/documentation/security/customizing-the-notarization-workflow)).
  Apple does not define “heavily”.
  This plan reads it as allowing UDZO, Apple’s own zlib format, and builds at
  `hdiutil`’s default zlib level rather than the maximum, level 9, that `make-dmg.sh`
  uses today, since an image of about 1 MB has little to gain from the maximum
  (`mb-4hwg` measures both).
  `release.sh` notarizes the app before packaging as well, so a copy dragged out of the
  image carries its own ticket; that is a second submission per release (Q7).
- **CI signing:** GitHub’s recipe creates a temporary keychain, imports the `.p12`, sets
  the key’s partition list so `codesign` can use it without a prompt, and puts the
  keychain on the search list; hosted runners are discarded after each job
  ([Sign Xcode applications](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications)).
  Its example imports with `-A`, which lets any application use the key; importing with
  `-T /usr/bin/codesign` is narrower.
  Its commands take the passwords as arguments.
  Environment secrets reach only jobs that name the environment, and only after a
  required reviewer approves; deployments can be limited to tags matching a pattern; by
  default administrators can bypass the protection rules; and when self-review is
  prevented, the person who started a run cannot approve it, which a sole maintainer
  must leave off
  ([Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments)).
  A required reviewer can also approve a waiting deployment through the REST API, which
  OAuth and classic tokens with `repo` scope can call
  ([Review pending deployments](https://docs.github.com/en/rest/actions/workflow-runs#review-pending-deployments-for-a-workflow-run)).
- **Provenance:** `actions/attest` v4 writes a signed build provenance attestation for
  files (`id-token: write`, `attestations: write`), free for public repositories; it
  needs a workflow’s OIDC token, so only a CI build can have one.
  `gh attestation verify FILE -R OWNER/REPO` accepts an attestation from any workflow in
  the repository, and `--signer-workflow` and `--source-ref` pin the workflow and the
  tag ([actions/attest](https://github.com/actions/attest), `gh attestation verify`
  manual). Immutable releases lock a published release’s assets and tag and give it a
  release attestation that `gh release verify` and `gh release verify-asset` check (gh
  2.98.0). An immutable release’s tag “cannot be deleted while the release exists”, and
  after the release is deleted the tag name cannot be reused
  ([Immutable releases](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases)).
  The setting is per repository and applies to every new release, the Python package’s
  included.
- **Updates:** Sparkle 2 verifies updates with EdDSA signatures from its appcast
  ([EdDSA](https://sparkle-project.org/documentation/eddsa-migration/)); its latest
  release is 2.10.1, and 2.9.5 and 2.9.6 fixed security issues
  ([releases](https://github.com/sparkle-project/Sparkle/releases)). Homebrew 5.0.0
  deprecated `--no-quarantine` and disabled official casks that fail Gatekeeper checks
  from September 2026 ([Homebrew 5.0.0](https://brew.sh/2025/11/12/homebrew-5.0.0)); it
  says nothing about third-party taps, but a quarantined download needs notarization
  anyway.
- **Verification tools:** Apple DTS’s recipe is `syspolicy_check distribution APP` on
  macOS 14 and later (on this Mac it prints “App passed all pre-distribution checks and
  is ready for distribution.”
  and exits 0 for a notarized third-party app); `spctl -a -t exec -vvv APP` and
  `spctl -a -t open -vvv --context context:primary-signature DMG`; and, for other code,
  `codesign -vvvv -R="notarized" --check-notarization`
  ([Testing a Notarised Product](https://developer.apple.com/forums/thread/130560),
  updated 2024-12-05). It calls these command-line checks a quick but less accurate test
  than the full one: a quarantined download on a fresh machine, ideally a VM restored
  from a snapshot, since Gatekeeper caches what it has seen.
  Two checks here are this plan’s own, not DTS’s: `codesign --verify --deep --strict`
  first, as `check-dmg.sh` does today, and `--check-notarization` on the app and the
  image, which the first signed build tests.
  `gktool scan` is a minimal Gatekeeper interface since macOS 14
  ([forum thread 706379](https://developer.apple.com/forums/thread/706379)).
- **Quarantine:** Apple DTS says “The on-disk structure of the `com.apple.quarantine`
  attribute is not considered API”, and points to
  [`URLResourceKey.quarantinePropertiesKey`](https://developer.apple.com/documentation/foundation/urlresourcekey/quarantinepropertieskey)
  as the supported way to quarantine a file
  ([forum thread 851710](https://developer.apple.com/forums/thread/851710)).
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

### Who Can Sign

The asset this plan protects is the Developer ID identity, with the notary credential
beside it. Two kinds of actor could misuse them: a compromised action or workflow change
in CI, and an agent session acting as the owner.
An agent runs as the owner’s macOS user on the build Mac and uses the owner’s GitHub
token through `gh` under the `github-editing` grant, so the owner steps gate it with
more than instructions where they can:

- **On the owner’s Mac,** the identity and the `metabrowser-notary` profile live in a
  dedicated release keychain, not the login keychain.
  It stays locked except during a release the owner started, when the owner unlocks it
  at a prompt, and it locks itself after 15 minutes idle and on sleep.
  The identity is imported with no application trusted to use it (neither `-A` nor
  `-T`), so each signing asks, and the owner answers “Allow”, never “Always Allow”,
  which would trust `codesign` with the key for good.
  The profile has no prompt of its own, since `notarytool` created it, so the lock is
  its gate. The doctor reports whether the keychain is unlocked (O1, O3, `mb-qu6j`).
- **In CI,** the `macos-release` environment’s required reviewer is the owner,
  administrators cannot bypass it, and the owner approves its deployments only in the
  web UI (O4). The REST API would accept an approval made with the owner’s token, so the
  agent rule below is an instruction there, not a control.
  The `check` job’s `main`-ancestry check means a hostile tag also needs a commit on
  `main` ([Release Flow](#release-flow)).
- **The agent rule,** in [Owner-Only Steps](#owner-only-steps): an agent never approves
  a deployment, never calls the pending-deployments endpoint, and signs or notarizes
  only during a release the owner started.

Signing on the owner’s Mac from the locked keychain is therefore the lower-exposure
path: each signing needs the owner’s answer at the Mac, and the profile works only while
the owner has the keychain unlocked.
That supports Q1’s answer, 0.1.0 signed locally.
CI signing keeps one residual risk, an injected agent approving a deployment through the
API, which the owner weighs again before the first CI release.

### Gap Table

| Item | Metabrowser | Current practice | Proposal |
| --- | --- | --- | --- |
| Developer ID Application identity | In the login keychain, not valid: G2 intermediate missing | G2-issued certificate; intermediate from Apple PKI | Owner moves it to the release keychain and installs the committed intermediate (O1); the doctor checks both (`mb-qu6j`) |
| Developer ID Installer identity | None | Installer packages only | Not needed |
| Hardened runtime, secure timestamp | Yes | Required | Keep; check the `runtime` flag and timestamp (`mb-4hwg`) |
| Entitlements | None, enforced | Only what is needed | Keep none |
| Notary credentials | Scripts take a profile or API key; none stored | API key; keychain profile locally | Owner creates a team key and stores its profile in the release keychain (O2, O3) |
| Pre-submission check | None | `syspolicy_check notary-submission` | Run before each submission (`mb-tfap`) |
| Notary log | Saved, not read | Read every log | Fail on errors and on a log that could not be read; print warnings (`mb-tfap`) |
| Stapling | App and DMG | Staple what is shipped | Keep (Q7) |
| DMG | UDZO at zlib level 9, signed, checksum, icon | UDZO, Developer ID, own identifier | Keep, at `hdiutil`’s default level (`mb-4hwg`) |
| Release assets | DMG and checksum | n/a | Keep, named in one place; the ZIP and manifest are `mb-5jr9` |
| Signing readiness | Preflight refuses, says little | n/a | A read-only doctor (`mb-qu6j`) |
| Image and app checks | Fails on misses | `syspolicy_check`, `spctl`, `stapler`, `--check-notarization` | Add the missing checks (`mb-4hwg`) |
| Quarantine and translocation | Reports quarantine; translocation untested | Quarantined download, fresh VM, later launch too | A release-download check (`mb-xd4o`) and a launch harness (`mb-u36j`) |
| CI release | Ad hoc rehearsal only | Tag-only job, environment secrets | A release workflow (`mb-mww5`) |
| Ephemeral keychain | None | Temporary keychain, partition list | A keychain script, rehearsed on every change (`mb-3ey5`) |
| Workflow guard | SHA pins checked | n/a | An allowlist for the release workflow (`mb-yqrs`) |
| Checksums and digests | `.sha256` | Digest shown by GitHub | Keep, and compare both (`mb-xd4o`) |
| Attestation | None | `actions/attest` | Attest a CI-built image (`mb-mww5`) |
| Immutable release | Off | Generally available | On before 0.1.0 (O5, Q3) |
| Release notes, Latest | Draft, not Latest | n/a | Keep; notes in the runbook (`mb-63cx`) |
| Updates | None; cask template | Cask now, Sparkle later | Recommend; owner decides (Q4, `mb-fl72`) |
| Homebrew cask | Rendered and checked, never linted | `brew style` and `brew audit` | Lint it in CI (`mb-eoez`); the tap and cask after the alpha’s first feedback (O6, Q5) |
| Icons | Variants enforced | n/a | Keep |
| End-to-end launch | Unit, live, and manual setup checks | Launch the built app; a quarantined launch on a clean Mac | A CI launch of the development build (`mb-epgm`) and the release’s launch harness (`mb-u36j`) |
| Architectures | arm64 | n/a | Keep arm64 (Q6) |
| Command-line link | Installs nothing | n/a | Keep |

### Release Flow

Both paths follow one order, so the tag exists before anything is signed and the owner
accepts a download before anything is published.
[macOS App Releases](../../publishing.md#macos-app-releases) holds the tag rule:

1. **Approve the commit.** The version change lands on `main`, and the owner approves
   `RELEASE_COMMIT`, its full SHA.
2. **Create the tag** on GitHub at that SHA with `gh api …/git/refs`, after checking
   that it is absent. It is never pushed from a clone.
   A draft does not create its tag, and `gh release create --verify-tag` refuses a
   missing one.
3. **Go ahead with notarization:** locally, the owner unlocks the release keychain; from
   CI, the owner approves the `macos-release` deployment in the web UI.
4. **Build, sign, notarize, and draft**, as below.
5. **Check the draft** with `make macos-check-release TAG=macos-vX.Y.Z BUILT=local` or
   `BUILT=ci`, then O8 on the draft’s download.
6. **Approve the image’s SHA-256 and the notes, and publish** the draft.

Once the tag exists it is permanent: a failure after step 2 that needs a change is
released under the next version, and a transient failure is retried at the same tag
([Failure Handling](../../publishing.md#failure-handling)).

Local, for 0.1.0, once O1 to O3 are done:

- `make macos-signing-check` reports every piece ready and the release keychain
  unlocked.
- `make macos-release SIGN_IDENTITY=… SIGN_KEYCHAIN=… APPLE_KEYCHAIN_PROFILE=metabrowser-notary`,
  run at `RELEASE_COMMIT`, builds, signs, notarizes and staples the app, packages,
  notarizes and staples the image, reads both notary logs, checks the image, and writes
  the checksum and cask.
  The owner locks the keychain when it finishes.
- `gh release create macos-vX.Y.Z --draft --verify-tag --latest=false` attaches the
  image and checksum, as the app README shows.
- Its provenance is the checksum, GitHub’s digest, and, once published with immutable
  releases on, the release attestation that `gh release verify-asset` checks.
  It has no build provenance attestation: only a workflow can make one, and a workflow
  that attested an image it did not build would claim a build that did not happen.

From CI, for the next release, once O4 is done: creating the tag starts
`.github/workflows/macos-release.yml`. Its `concurrency` group is the tag’s ref, with
`cancel-in-progress: false`, so a second run for the same tag, such as a re-run, waits
instead of cancelling one that is signing.

1. **`check`**, with no environment and `contents: read` only, validates the tag against
   `macos-v$(cat apps/macos/VERSION)` and that its commit is on `main`, and ends the run
   when the tag’s release already has assets.
2. **`sign`** needs `check`, waits for the owner’s approval of the `macos-release`
   environment in the web UI, then checks out the tag, imports the identity and the
   committed G2 intermediate into a temporary keychain with a random password generated
   in the job, writes the API key to a mode 0600 file, runs the signing doctor, runs
   `make macos-release`, deletes the keychain and the key (`always()`), and uploads the
   image and checksum. Permissions: `contents: read` only.
3. **`draft`** needs `sign`, holds no Apple secrets, attests the image, and creates the
   draft release with `--verify-tag --latest=false`. Permissions: `contents: write`,
   `id-token: write`, `attestations: write`.
4. The owner runs or watches `make macos-check-release BUILT=ci` on the draft, which
   also verifies the attestation, then does O8 and publishes.

Once the release workflow exists, a release built locally is the exception: its tag
starts a run that waits at the approval, which the owner rejects, so the job ends
without secrets. The asset names, today the image and its checksum, come from one
function in `common.sh` that `release.sh`, the workflow’s upload and attestation, and
`check-release.sh` all use.
`publish.yml` still runs its job only for `v` tags, so neither path reaches PyPI.

### Components

- `apps/macos/scripts/check-signing.sh` and `make macos-signing-check`: new.
- The G2 intermediate certificate under `apps/macos/packaging/`: new, a public file.
- `apps/macos/scripts/build-app.sh`, `make-dmg.sh`, `notarize.sh`, and `release.sh`:
  take `SIGN_KEYCHAIN`.
- `apps/macos/scripts/check-dmg.sh` and `notarize.sh`: extended.
- `apps/macos/scripts/check-release.sh` and `make macos-check-release`: new, with a
  small Swift helper that sets a simulated quarantine.
- `apps/macos/scripts/ci-keychain.sh`: new; used by both workflows.
- `.github/workflows/macos-release.yml`: new.
  `macos-app.yml`: rehearses the keychain script, launches the development build, and
  lints the cask.
- `devtools/check_supply_chain.py` and its tests: an allowlist for the release workflow.
- `apps/macos/README.md`, `docs/publishing.md`, `SUPPLY-CHAIN-SECURITY.md`: the runbook,
  the release checklist, and the reviews of each new action, Homebrew, and the committed
  certificate.

### API Changes

None. No route, model, or `metab` command changes; the scripts and Make targets are the
app’s internal release tooling.

## Implementation Plan

Each agent-implementable step is a bead under `mb-hl2i`. `mb-e9fm` depends on `mb-63cx`,
`mb-mww5`, and `mb-eoez`, which close its first signed release, its release workflow,
and its cask.

| Bead | Step | Phase | Depends on |
| --- | --- | --- | --- |
| `mb-qu6j` | A read-only signing doctor and the release keychain | 1 | none; lands first, alone |
| `mb-4hwg` | Gatekeeper checks in `check-dmg.sh` | 1 | none |
| `mb-tfap` | Check before submitting; read the notary log | 1 | none |
| `mb-xd4o` | Check a release as a downloader gets it | 1 | `mb-4hwg` |
| `mb-u36j` | Launch a downloaded release, translocated | 1 | `mb-xd4o` |
| `mb-63cx` | The release runbook | 1 | `mb-qu6j`, `mb-4hwg`, `mb-tfap`, `mb-xd4o`, `mb-u36j` |
| `mb-3ey5` | An ephemeral CI keychain script | 2 | `mb-qu6j` |
| `mb-yqrs` | An allowlist for the release workflow | 2 | none |
| `mb-mww5` | The release workflow | 2 | `mb-qu6j`, `mb-4hwg`, `mb-tfap`, `mb-xd4o`, `mb-3ey5`, `mb-yqrs` |
| `mb-eoez` | Lint the generated cask in CI | 2 | none |
| `mb-epgm` | Launch the development build in CI | 2 | none |

### Owner-Only Steps

**Owner only.** These use the owner’s Apple account, private keys, or repository
settings. An agent never types, stores, or prints a secret.
It signs or notarizes only during a release the owner started, after the owner’s
go-ahead.
It never approves a deployment and never calls the pending-deployments endpoint
(`POST /repos/{owner}/{repo}/actions/runs/{run_id}/pending_deployments`): the owner
approves `macos-release` deployments only in the web UI ([Who Can Sign](#who-can-sign)).

`mb-qu6j` lands and runs first, and each step below fixes what its report names.

- [ ] **O1. Set up the release keychain** on the build Mac:
  - Install the G2 intermediate, “Developer ID - G2”, into the login keychain from the
    copy committed under `apps/macos/packaging/` (`mb-qu6j`), which came from
    [Apple PKI](https://www.apple.com/certificateauthority/). It is a public
    certificate, and `codesign` builds the chain only from keychains on the search list.
  - Create the release keychain with
    `security create-keychain ~/Library/Keychains/metabrowser-release.keychain-db`,
    typing its password at the prompt (never `-p`); keep it on the user search list; and
    make it lock on sleep and after 15 minutes idle with
    `security set-keychain-settings -l -u -t 900` on it.
  - Move the Developer ID Application identity into it: export it from the login
    keychain as a `.p12`; import it with `security import FILE -k KEYCHAIN`, with
    neither `-A` nor `-T`, typing the `.p12` password in the dialog; delete the identity
    from the login keychain; and delete the `.p12`, or keep it offline as the identity’s
    only backup.
  - Confirm `security find-identity -v -p codesigning` lists one valid identity.
    Each signing then asks for the key: answer “Allow”, never “Always Allow”.
  - Lock it with `security lock-keychain KEYCHAIN` whenever no release is running.

- [ ] **O2. Create an App Store Connect API key** for notarization at
  https://appstoreconnect.apple.com/access/api: a team key with the Developer role (Q2),
  which developers report suffices.
  Its `.p8` can be downloaded only once.
  Accept any pending developer agreement first: `man notarytool` says the notary service
  serves developers who accepted the relevant agreements when it describes app-specific
  passwords, and this plan assumes the same holds for API keys.

- [ ] **O3. Store the notary profile** in the release keychain, test it, and then delete
  the `.p8`, so the profile is the key’s only copy on the Mac:

  ```shell
  xcrun notarytool store-credentials metabrowser-notary \
    --key AuthKey_KEYID.p8 --key-id KEYID --issuer ISSUER_UUID \
    --keychain ~/Library/Keychains/metabrowser-release.keychain-db
  xcrun notarytool history --keychain-profile metabrowser-notary \
    --keychain ~/Library/Keychains/metabrowser-release.keychain-db
  ```

- [ ] **O4. For CI signing, before the next release (Q1):**
  - export the identity from the release keychain as a `.p12` with a strong password;
  - create a second team API key, for CI only, as in O2, so each key can be revoked
    alone;
  - create the `macos-release` environment with the owner as required reviewer,
    self-review allowed, “Allow administrators to bypass configured protection rules”
    turned off, and deployments limited to tags matching `macos-v*`;
  - add environment secrets, never repository secrets, for the base64 `.p12`, its
    password, the identity name, the CI key’s `.p8` contents, its key ID, and the issuer
    ID;
  - delete the exported `.p12` and the downloaded `.p8`; the `.p12` password then lives
    only in its secret.

- [ ] **O5. Repository settings, before 0.1.0 is published (Q3):** turn on immutable
  releases, add a tag ruleset that stops `v*` and `macos-v*` tags being moved or
  deleted, and optionally turn on the “require actions to be pinned to a full-length
  commit SHA” policy.

- [ ] **O6. Create the tap repository and publish the cask** after the alpha’s first
  round of feedback, not with 0.1.0 (Q5).

- [ ] **O7. Approve each release,** in this order:
  1. the exact `RELEASE_COMMIT`, after which its tag is created
     ([macOS App Releases](../../publishing.md#macos-app-releases));
  2. the go-ahead for its notarizations: locally, by unlocking the release keychain;
     from CI, by approving the `macos-release` deployment in the web UI;
  3. O8 on the draft’s download;
  4. the image’s SHA-256 and the notes, and then publication of the draft.

- [ ] **O8. Open the draft’s image** from a browser download on a Mac or VM that has not
  run the app, answer Gatekeeper’s prompt, and launch once offline, before the draft is
  published.

- [ ] **O9. Renew the certificate every year.** G2 certificates last one year, so before
  expiry (the doctor warns 90 days ahead) the Account Holder creates the next Developer
  ID Application certificate, imports it into the release keychain as in O1, and, once
  CI signs, replaces O4’s `.p12` secrets with a fresh export.

**After a leak** of an API key or the identity: revoke the API key in App Store Connect,
delete the environment secrets, ask Apple to revoke the certificate and the notarization
tickets of what the leaked key signed
([Notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)),
and replace what was revoked (O2 to O4, O9).

### Phase 1: Local Release Readiness

Everything here works without secrets, and makes the first release safe to build on the
owner’s Mac.

- [ ] **`mb-qu6j` A signing doctor and the release keychain.** It lands first, alone,
  and runs on the build Mac before O1 to O3, so its report directs them.
  `scripts/check-signing.sh`, run by `make macos-signing-check`, is read-only and never
  unlocks a keychain or prompts.
  It checks:
  - a valid Developer ID Application identity in the release keychain that
    `SIGN_KEYCHAIN` names (by default
    `~/Library/Keychains/metabrowser-release.keychain-db`), with a warning when one is
    also in the login keychain;
  - that keychain on the search list, its lock settings, and whether it is unlocked now;
  - the certificate’s issuer and whether that intermediate is installed and matches the
    committed copy, naming “Developer ID - G2” and Apple PKI when it is not;
  - days to expiry, failing under 30 and warning under 90, and that `SIGN_IDENTITY`,
    when set, matches;
  - Xcode and `notarytool` versions, the notary profile in the release keychain or the
    API key variables, and with `ONLINE=1` a `notarytool history` call.

  Each miss names its owner step.
  The bead also commits the G2 intermediate under `apps/macos/packaging/` with its
  SHA-256 and a `SUPPLY-CHAIN-SECURITY.md` entry that records where it came from and
  that it chains to the system’s Apple Root CA. It makes `build-app.sh` and
  `make-dmg.sh` pass `codesign --keychain "$SIGN_KEYCHAIN"`, makes `notarize.sh` pass
  `--keychain` with the profile, and has `release.sh`’s preflight call the doctor.

- [ ] **`mb-4hwg` Gatekeeper checks in `check-dmg.sh`.** For a Developer ID build: the
  hardened runtime flag (`flags=…(runtime)` in `codesign -dvvv`), a secure timestamp,
  the Team ID matching `EXPECTED_TEAM_ID` when set, the full chain
  (`Developer ID Application`, `Developer ID Certification Authority`, `Apple Root CA`),
  `syspolicy_check distribution` on the app, and
  `codesign -R="notarized" --check-notarization` on the app and image beside the
  existing `stapler` and `spctl` checks; with `NOTARIZE=1` every one is required.
  DTS gives `--check-notarization` for other code, so its use on an app and an image is
  this plan’s extension, which the first signed build tests.
  A quarantine attribute, when present, is decoded (flags, time, agent) and printed as
  information only, never as a pass or a fail, since its format is not API.
  `make-dmg.sh` builds at `hdiutil`’s default zlib level instead of level 9, after
  measuring both, and says why beside the command.

- [ ] **`mb-tfap` Check before submitting, and read the notary log.** Before each
  submission, `notarize.sh` runs `syspolicy_check notary-submission` on the app, or on
  the app inside the image, and stops on a failure, so a rejection costs no round trip
  against the daily limit.
  After each submission it fetches the log, retrying, and reads it with `plutil`: it
  fails on any issue of severity `error`, prints each warning with its path, and prints
  the submission ID, status, and counts in one line for the release record.
  Under `NOTARIZE=1`, a log it could not fetch or parse is fatal.

- [ ] **`mb-xd4o` A release-download check.** `scripts/check-release.sh`, run by
  `make macos-check-release TAG=… BUILT=local|ci`, for a draft or published release:
  - downloads the assets with `gh release download` into a scratch folder;
  - checks `shasum -a 256 -c` and the asset digest from `gh release view --json assets`;
  - with `BUILT=ci`, requires the build provenance attestation, verified with
    `gh attestation verify --signer-workflow jlevy/metabrowser/.github/workflows/macos-release.yml --source-ref refs/tags/macos-vX.Y.Z`;
  - once the release is published, checks the immutable release with
    `gh release verify-asset`;
  - applies a quarantine attribute if the download has none, through
    `URLResourceKey.quarantinePropertiesKey` with a small Swift helper, labelled a
    simulation;
  - runs `check-dmg.sh` with `NOTARIZE=1`;
  - prints which provenance it verified.

  The build kind is an input, not inferred, so a CI build that lost its attestation
  cannot pass as a local one.

- [ ] **`mb-u36j` Launch a downloaded release, translocated.** `LAUNCH=1` on the same
  target, after the download check passes, copies the app out of the image into a
  scratch Downloads folder, still quarantined, opens it, waits for the person at the Mac
  to answer Gatekeeper, checks that the process runs from an `/AppTranslocation/` path
  and shows the launch notice, quits, relaunches and records whether it is still
  translocated, then moves the app and checks a launch from the new place (measuring
  whether a move from Terminal clears translocation as a move in Finder does).
  The launch runs the unmodified release bundle, whose identity is the installed
  release’s, so the script refuses to run while a release copy is running.
  It backs up and restores that identity’s defaults, the shared `session.json`, and its
  recent-documents list, and unregisters each scratch copy with `lsregister -u`, as
  `check-setup-flows.sh` does; on a VM or a separate account it needs none of that.

- [ ] **`mb-63cx` The release runbook.** `apps/macos/README.md` Building a Release: the
  owner steps O1 to O9 and the leak step, the doctor, the checks, the test matrix
  (fresh, upgrade, duplicate, another account, moved and not moved), the notes template,
  and the approval record.
  The matrix runs as part of the clean-account matrix (`mb-5fp7`), which the runbook
  links rather than repeats.
  `docs/publishing.md`: the app release in the release checklist; its tag rule and
  failure handling are already there.

### Phase 2: Release From CI

- [ ] **`mb-3ey5` An ephemeral keychain script.** `scripts/ci-keychain.sh`, with
  `create`, `import`, and `cleanup` commands: a keychain in `RUNNER_TEMP` with a
  password generated in the job, the identity imported with `-T /usr/bin/codesign` and a
  partition list of `apple-tool:,apple:,codesign:`, the committed G2 intermediate
  imported so the job downloads nothing, the keychain first on the user search list, the
  API key written to a mode 0600 file in `RUNNER_TEMP`, and cleanup that deletes the
  keychain and the key and restores the list.
  As in GitHub’s recipe, the passwords reach `security` as arguments, which holds only
  on a runner discarded after the job; the script turns shell tracing off and never
  echoes them. `macos-app.yml` rehearses it on every change with a throwaway self-signed
  identity: the import succeeds, `security find-identity` lists the identity, and
  cleanup leaves nothing.

- [ ] **`mb-yqrs` An allowlist for the release workflow.** It lands with or before
  `mb-mww5`, so the workflow never exists without its guard.
  `devtools/check_supply_chain.py` parses the workflows with PyYAML, already a
  dependency, which reads the `on:` key as `True`, and requires the allowed shape
  instead of refusing listed ones:
  - the release workflow’s only trigger is `push` with `tags: [macos-v*]` and no
    branches;
  - the job naming the `macos-release` environment has exactly `contents: read`, uses
    only allowlisted actions, and runs only `make macos-*` targets and scripts under
    `apps/macos/scripts/`;
  - no workflow-level write permissions;
  - no other workflow names the environment.

  Tests in `tests/` cover each refused shape on fixture workflows, and the real workflow
  passes once `mb-mww5` adds it.

- [ ] **`mb-mww5` The release workflow.** `.github/workflows/macos-release.yml` as in
  [Release Flow](#release-flow): `push` of `macos-v*` tags only; the `check`, `sign`,
  and `draft` jobs with their permissions; `concurrency` per ref with
  `cancel-in-progress: false`; a full clone for the build number;
  `persist-credentials: false`; a timeout above two notarizations; actions pinned by
  full SHA and reviewed in `SUPPLY-CHAIN-SECURITY.md`; the notary logs kept as workflow
  artifacts, not release assets; and the asset names from `common.sh`. It confirms once
  that a tag created through `gh api` with the owner’s token starts the workflow: refs
  created with `GITHUB_TOKEN` start none, and the user-token case is unverified here.

- [ ] **`mb-eoez` Lint the cask in CI.** `macos-app.yml` runs `brew style` and an
  offline `brew audit --cask` on the rendered rehearsal cask in a scratch tap, with
  `HOMEBREW_NO_AUTO_UPDATE=1`, so a template change that Homebrew would reject fails
  before a release. Homebrew otherwise updates itself on first use and installs its own
  Ruby gems for `style`, so the bead records its review in `SUPPLY-CHAIN-SECURITY.md`,
  and Homebrew never runs in the release workflow.
  It can land before the cask ships (Q5).

- [ ] **`mb-epgm` Launch the development build in CI.** After `make macos-app`,
  `macos-app.yml` opens the development bundle on a scratch folder, waits for its server
  to answer, quits, and checks that no server process is left.

## Testing Strategy

| Step | How it is verified |
| --- | --- |
| O1 | `make macos-signing-check` reports the identity valid in the release keychain and absent from the login keychain, the G2 intermediate present, expiry over 90 days, and the keychain locked when no release runs |
| O2, O3 | The doctor with `ONLINE=1`, with the keychain unlocked, gets an answer from `notarytool history` |
| O4 | The environment’s settings show the bypass off and the tag pattern; the first CI release’s `sign` job waits for the owner’s approval |
| O5 | `gh api` shows immutable releases on and the tag ruleset active |
| `mb-qu6j` | Run on the build Mac before O1 to O3, it must report exactly the missing release keychain, the missing G2 intermediate, and the missing profile, and that report is recorded; `test-scripts.sh` feeds it recorded `security` and `openssl` output for valid, missing-intermediate, expiring, mismatched, locked, and unlocked cases |
| `mb-4hwg` | `test-scripts.sh` checks the new readers on copies of a system binary signed ad hoc with and without `--options runtime`; CI runs the extended `check-dmg.sh` on both images; the Developer ID branch is proven by the first signed build; the zlib measurements are recorded in `make-dmg.sh` |
| `mb-tfap` | `test-scripts.sh` runs the log reader on fixture logs: accepted with no issues, accepted with a warning, invalid with an error, and, under `NOTARIZE=1`, a missing and an unparsable log; the pre-submission check is proven by the first signed build |
| `mb-xd4o` | Run with `BUILT=local` on the 0.1.0 draft before it is published and again once published, and with `BUILT=ci` on the first CI draft; `test-scripts.sh` shows a missing attestation failing `BUILT=ci` |
| `mb-u36j` | Run by the owner on the 0.1.0 draft, on a VM or a second account if possible |
| `mb-63cx` | `make format` and `make lint-check` (public hygiene included) pass; the owner follows the runbook for the first release |
| `mb-3ey5` | The rehearsal in `macos-app.yml` passes, and a deliberate failure in import still leaves cleanup run |
| `mb-yqrs` | Unit tests in `tests/` for each refused shape, and the real workflow passes |
| `mb-mww5` | The first `macos-v*` tag after O4 produces a draft whose image passes `make macos-check-release BUILT=ci`; until then, `check_supply_chain.py` and a review of the workflow |
| `mb-eoez` | The lint step passes on the rehearsal cask, and fails in a test run on a cask with a malformed `url` stanza, which `brew style` or the offline audit reports |
| `mb-epgm` | The step passes in CI, and fails in a test run on a deliberately broken launch |

## Rollout Plan

1. `mb-qu6j` lands alone.
   The agent runs it on the build Mac and records its report, the owner does O1 to O3 as
   it directs, and the agent reruns it until every piece is ready.
2. The rest of Phase 1 lands as one stack, and the owner does O5. The first release,
   `macos-v0.1.0` as an alpha, follows [Release Flow](#release-flow) on the owner’s Mac:
   the commit approved, the tag created, the keychain unlocked for the build, the draft
   checked with `BUILT=local` and `mb-u36j`’s launch, O8, then publication.
3. Phase 2 lands as a second stack, `mb-yqrs` with or before `mb-mww5`. After O4, the
   next app release is the first from CI, checked from its draft with `BUILT=ci`.
4. The tap and the cask follow the alpha’s first round of feedback (O6, Q5).

## Risks

- **An agent acting as the owner** runs as the owner’s macOS user and uses the owner’s
  GitHub token. Locally, the locked release keychain and a prompt for each signing gate
  it. In CI, the REST API accepts a deployment approval made with that token, so the
  agent rule is an instruction there, not a control; a hostile tag also needs a commit
  on `main`. Signing 0.1.0 on the owner’s Mac avoids that exposure, and the owner weighs
  it again before the first CI release ([Who Can Sign](#who-can-sign)).
- **A signing key in CI** can be stolen by a compromised action or workflow change.
  The environment approval, the tag-only trigger, SHA pins, no package installs in the
  signing job, and deleting the keychain at once bound it; signing only on the owner’s
  Mac removes it. Notarization tickets can be revoked for versions signed by a stolen key
  ([Notarizing macOS software](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)).
- **Gatekeeper caches** what the build Mac has seen, so a local first-launch check can
  pass where a clean Mac would not; Apple DTS recommends a fresh VM for the real test.
- **A simulated quarantine attribute** may not match a browser download.
  The helper sets it through the supported interface, and the owner’s browser download
  (O8) is the acceptance test.
- **The translocation check runs the real release identity**, whose defaults, saved
  session, and recent documents the owner may use; the script’s backup and refusal guard
  that, and a VM avoids it.
- **Immutable releases and the tag ruleset make versions permanent.** A defective
  published image needs a new patch version, as on PyPI, and the setting covers the
  Python package’s releases too.
  A `publish.yml` failure that needs a code or workflow change spends `vX.Y.Z`, since
  the workflow runs from the tagged commit and the tag cannot be reused.
  An app tag is created before signing, so a rejected notarization or a draft that fails
  its check needs a new version as well; only a transient failure is retried at the same
  tag ([Failure Handling](../../publishing.md#failure-handling)).
- **Two notarizations per release** double the wait and count against 75 a day; Apple’s
  simplest path notarizes the DMG only, and loses the dragged-out app’s own ticket (Q7).
- **The certificate term:** new G2 certificates last a year, so renewal is a yearly
  owner step (O9); the doctor warns 90 days ahead.
- **Command-line checks are less accurate** than a quarantined download on a fresh
  machine, Apple DTS says
  ([Testing a Notarised Product](https://developer.apple.com/forums/thread/130560)), so
  O8 and `mb-u36j` are the real test.
  The API key role for notarization is undocumented; if the Developer role fails, O2
  needs another.
- **macOS runner images** may or may not carry the G2 intermediate; the keychain script
  imports the committed one.

## Open Questions

- **Q1. Where to sign.** Decided 2026-11-16: sign and notarize 0.1.0 on the owner’s Mac
  with the existing scripts; the tag-triggered CI release workflow follows for the next
  release. [Who Can Sign](#who-can-sign) weighs the agent exposure: local signing from
  the locked release keychain is the lower-exposure path, which supports the answer, and
  CI signing’s residual risk is weighed again before the first CI release.
- **Q2. Notary credential.** Decided 2026-11-16: an App Store Connect team API key with
  the Developer role and its issuer ID, stored as the `metabrowser-notary` profile (O2,
  O3).
- **Q3. Immutable releases.** Decided 2026-11-16: turn them on before 0.1.0 is published
  (O5). They cover the Python package’s releases too.
  With the tag ruleset, every published version and every `macos-v*` tag is permanent: a
  `publish.yml` failure that needs a code or workflow change spends its version, and so
  does an app release whose notarization or draft check fails after its tag exists
  ([Failure Handling](../../publishing.md#failure-handling)).
- **Q4. Updates for the alpha** (open; `mb-fl72` tracks them): recommendation: the
  Homebrew cask in a personal tap plus the release page, and an in-app “update
  available” notice from the GitHub releases API next; Sparkle 2 (2.10.1 or later, EdDSA
  keys held by the owner) once app releases are frequent enough that a notice is a
  burden. The decision sets `mb-fl72`’s scope.
- **Q5. The cask.** Decided 2026-11-16: no cask with 0.1.0; the tap and the cask follow
  the alpha’s first round of feedback (O6). The lint (`mb-eoez`) can land before then.
- **Q6. Architectures** (open): arm64 only, as now?
  Recommendation: yes for the alpha; `ARCHES="arm64 x86_64"` builds a universal image if
  feedback asks for Intel Macs.
- **Q7. Notarize twice or once** (open): keep notarizing the app before packaging, so a
  dragged-out copy launches offline, or notarize only the DMG, as Apple’s simplest path
  does? The ZIP and manifest the native plan puts beside the DMG (`mb-5jr9`), from which
  `metab` would install the app (`mb-92d9`), bear on it: a ZIP cannot carry a ticket, so
  an app in one launches offline only if the app itself was stapled.
  Recommendation: keep both submissions.
- **Q8. Who creates the tag** (open): after the owner approves `RELEASE_COMMIT`, does
  the agent or the owner run the `gh api` command that creates the `macos-v*` tag
  ([macOS App Releases](../../publishing.md#macos-app-releases))? Recommendation: the
  agent, as it creates the Python package’s tag; from Phase 2 that command starts the
  release workflow, whose deployment only the owner approves, in the web UI.

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
  [Apple PKI](https://www.apple.com/certificateauthority/),
  [`URLResourceKey.quarantinePropertiesKey`](https://developer.apple.com/documentation/foundation/urlresourcekey/quarantinepropertieskey)
- Apple DTS:
  [Testing a Notarised Product](https://developer.apple.com/forums/thread/130560),
  [App Translocation Notes](https://developer.apple.com/forums/thread/724969),
  [Resolving Gatekeeper Problems](https://developer.apple.com/forums/thread/706379),
  [a missing intermediate](https://developer.apple.com/forums/thread/705473),
  [supported quarantine handling](https://developer.apple.com/forums/thread/851710)
- GitHub:
  [Sign Xcode applications](https://docs.github.com/en/actions/how-tos/deploy/deploy-to-third-party-platforms/sign-xcode-applications),
  [Deployments and environments](https://docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments),
  [Review pending deployments](https://docs.github.com/en/rest/actions/workflow-runs#review-pending-deployments-for-a-workflow-run),
  [Artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations),
  [actions/attest](https://github.com/actions/attest),
  [Immutable releases](https://docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases),
  [immutable releases changelog](https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/),
  [asset digests](https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/),
  [SHA-pinning policy](https://github.blog/changelog/2025-08-15-github-actions-policy-now-supports-blocking-and-sha-pinning-actions/)
- Updates: [Sparkle releases](https://github.com/sparkle-project/Sparkle/releases),
  [Sparkle EdDSA](https://sparkle-project.org/documentation/eddsa-migration/),
  [Homebrew 5.0.0](https://brew.sh/2025/11/12/homebrew-5.0.0),
  [Acceptable Casks](https://docs.brew.sh/Acceptable-Casks)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
