---
type: is
id: is-01m7zxaqehf7tth92g7q9b68x6
title: Assess first macOS release readiness and the open Metabrowser PRs
kind: task
status: closed
priority: 1
version: 7
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/520
    at: 2026-11-21T20:49:45.673Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/570
    at: 2026-11-21T20:49:45.674Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/677
    at: 2026-11-21T20:49:45.674Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/679
    at: 2026-11-21T20:49:45.674Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/247
    at: 2026-11-21T20:54:39.215Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/380
    at: 2026-11-21T20:54:39.216Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/44952503499
    at: 2026-11-21T21:42:53.101Z
  - kind: other
    url: https://github.com/jlevy/metabrowser/actions/runs/44952503515
    at: 2026-11-21T21:42:53.102Z
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
hold: null
hold_until: null
created_at: 2026-11-21T20:38:55.695Z
updated_at: 2026-11-21T21:42:53.102Z
started_at: 2026-11-21T20:40:37.197Z
closed_at: 2026-11-21T20:58:08.752Z
close_reason: Assessed all 14 original open PRs, verified release prerequisites, compared Kerm’s historical download, and recorded the launch and publication gates. Each implementation fix has its own bead.
resolution: null
duplicate_of: null
---
Review all open Metabrowser PRs at pinned heads for standalone stabilization changes. Hold FDU and the document model redesign. Compare the native packaging and publication path with Kerm, run the signing doctor, and record the gates for signing, Gatekeeper, and a clean-user download.

## Notes

## First macOS release assessment

Reviewed against main `c7e02acd649df3be6e0b5f1b630ca0fe9899771e` on 2026-11-21. Exact main CI passed. The latest native rehearsal passed at `431199ab6` and verified ad-hoc arm64 app and DMG packaging. No `macos-v*` tag or GitHub release exists. The first app release is `macos-v0.1.0`, Apple silicon, macOS 26 or later, with a separately installed `metab` 0.13.0 or later.

1. Publish a compatible KPress containing jlevy/kpress#80, then adopt the reviewed indexed release in Metabrowser (mb-d515). KPress 0.3.8 is currently the newest indexed release. Main sets an unreleased KPress floor and resolves its Git commit through `[tool.uv.sources]`; the PyPI workflow refuses source overrides. Respect the owner's KPress acceptance step recorded in mb-tbq9.
2. Assemble the 0.13.0 runtime prep PR and changelog, complete exact-candidate distribution, performance, manual and workflow gates, obtain the runtime release approval, publish through existing PyPI trusted publishing, and verify the indexed wheel in a fresh uv tool environment (mb-brvm, mb-icss, mb-b246). Verify installed `metab --doctor`, plugins and plain SQLite, including a live WAL database without the optional fsqlite integration. Then land the app change that enables `MetabRequirement.isReleased` and updates the README and installation pages (mb-1d8p).
3. On the build Mac, Xcode 26.6 and notarytool were present. The read-only doctor reported three misses: the dedicated release keychain, Apple Developer ID G2 intermediate on the keychain search path, and the notary profile. The owner provisions and verifies the Developer ID Application identity and App Store Connect notary credentials in the release keychain (mb-21t6). GitHub immutable releases are off and the rulesets list is empty. Complete the owner setup in the release runbook before using an approved tag. The first release uses the documented local signing path. CI signing, cask publication and an updater have their own later decisions.
4. On the approved clean source SHA, use the committed release icon and shared license, SwiftPM/Xcode 26.6, and the default arm64 target. Run the candidate native suite, WebKit gate and ad-hoc release rehearsal. Create the permanent macOS tag at the approved SHA. With the owner-unlocked release keychain, `make macos-release` signs with Developer ID, hardened runtime and a timestamp, notarizes and staples the app, packages it in a compressed DMG with the Applications link and volume icon, signs, notarizes and staples the DMG, and recomputes the SHA-256 after stapling. Record both Apple notary submissions and run the strict signature and Gatekeeper checker.
5. Attach exactly the signed DMG and checksum to a GitHub draft with `--verify-tag --latest=false`. Verify the actual download with `make macos-check-release BUILT=local` and expected Team ID. Exercise the launch harness with `LAUNCH=1` as a supplementary test. Its current-home LaunchServices and WebKit history can persist. In a genuinely fresh Apple-silicon/macOS 26 standard account or VM, download in a browser, first-launch offline, move to Applications in Finder and relaunch. Test CLI-first and app-first missing/old runtime paths without Xcode or CLT, restart, Settings plugins, local folders, public and private GitHub as configured, ordinary SQLite, and download/install with an administrator account. Test replacement or duplicate behavior with the preview and sign-off as appropriate (mb-5fp7). Retain the candidate SHA, final DMG hash, Apple logs and test evidence. Publish after owner approval, preserve the Python release's Latest status, then verify the immutable release and both association checks again.
6. Kerm's repository shows working arch-specific DMGs uploaded to GitHub. Its check script surfaces quarantine information and inspects an embedded app. The release checker can print signature, policy or detach failures and finish with exit zero. The historical Kerm 0.1.1-dev2 arm64 image passed image integrity verification, was unsigned as a container, and had no attached DMG ticket. The host denied a read-only attach, so the embedded app signature was not independently verified. Use Kerm's browser-download metadata as diagnostics. Keep Metabrowser's strict verification, asset digest and notarization controls. See the existing macOS publishing runbook.

## Open pull request sweep

The fourteen open PRs at the start of the sweep were assessed for independent release fixes. The stack diffs were inspected at their pinned heads. This was a landing-scope review, with candidate-specific test evidence reported in the separate stabilization PR reviews.

- #247 `b10a2fa8` is tagged reference for retired hosted-review and provider interfaces. Its pinned prior review and retained tag are adequate. No release change.
- #380 `e0220b65` is plugin source and process architecture. Its Phase 0 home-variable and compatible dependency-range items already have mb-eazg and mb-hi06. Existing default app setup and its doctor warning can ship. Repository trust and optional process isolation need their own design decision.
- #498 `1b453938` is the FDU feasibility and evidence layer. #501 `a0e9f330` selects a test provider. #502 `6c655fdf` introduces provider test seams, and moves the ETag contention hold earlier than main's intended contention case. #503 `bf1c091d` adds benchmark comparison that can accept equally truncated runs. #507 `b2030fab` records provider decisions, with registry tests accepting any known status per row. These layers are in formal stack #682.
- #508 `36d0a91f` adds a strict expected failure that exposed a stale directory timestamp on current main. Extracted a passing regression and one production assignment independently as #686 (mb-6fme). The broader conformance changes remain on #682.
- #518 `17b24a46` waits on publication receipts under the operation lease. #519 `f9f6d07d` resets restart budget per failed handle and has unbounded reopen and relay operations. #520 `b56afdc0` groups permanent and transient provider failures into a common retry response. Current-main version pin exhaustion has a separate HTTP/SSE opportunity tracked in mb-fhw6. No FDU architecture work is part of this release.
- #570 `21ad253d` and #679 `4d022660` are formal stack #681. The broad object/view model plan and the dependent collection document design remain for a later decision. The minor native plan wording about shipped `--present` can be corrected independently when that plan is updated.
- #677 `1ec0dc62` supersedes closed #599 and conflicts with current main in CLI goldens. Its changes depend on the new Guided PR feature. Keep the draft out of the release.

Additional focused release work is individually tracked in #687 (setup smoke), #688 (download attachment verification), and #689 (bundle provenance). Architecture override normalization and the optional quarantine diagnostic fixture are mb-im90 and mb-b2nw.
