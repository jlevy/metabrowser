---
type: is
id: is-01m7k2w8wrwrypxm2vxyqaaa8v
title: "macOS app: a read-only signing doctor and the release keychain (make macos-signing-check)"
kind: task
status: closed
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m7k2xcrjxtgfe2mepxas1434
  - type: blocks
    target: is-01m7k2xdgr9b8sra4vrd372fe2
  - type: blocks
    target: is-01m7k2wzxnnfkzcr7eg8ngptcq
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:05:45.879Z
updated_at: 2026-11-17T22:23:17.692Z
started_at: 2026-11-17T07:36:57.257Z
closed_at: 2026-11-17T22:23:17.692Z
close_reason: "Landed in the macOS tooling stack #509+#510 (reviews A and B addressed, green incl. macOS CI), merged to main at b5e986d0b on 2026-11-17."
resolution: null
duplicate_of: null
---
Phase 1 of the publishing plan; lands first, alone, and runs on the build Mac before the owner's O1-O3, so its report directs them (PR #485 A4). Add apps/macos/scripts/check-signing.sh and make macos-signing-check, read-only, never unlocking a keychain or prompting: a valid Developer ID Application identity in the release keychain SIGN_KEYCHAIN names (default ~/Library/Keychains/metabrowser-release.keychain-db), warning when one is also in the login keychain; that keychain on the search list, its lock settings, and whether it is unlocked now (PR #485 A1); the certificate's issuer and whether that intermediate is installed and matches the committed copy (naming Developer ID - G2 and Apple PKI when not); days to expiry (fail under 30, warn under 90); SIGN_IDENTITY matches when set; Xcode and notarytool versions; the notary profile in the release keychain or the API key variables, and with ONLINE=1 a notarytool history call. Each miss names the owner step that fixes it. Also: commit the G2 intermediate under apps/macos/packaging/ with its SHA-256 and a SUPPLY-CHAIN-SECURITY.md entry recording its source and that it chains to the system Apple Root CA (PR #485 A21); build-app.sh and make-dmg.sh pass codesign --keychain "$SIGN_KEYCHAIN", notarize.sh passes --keychain with the profile, and release.sh's preflight calls the doctor. Done when its report on today's build Mac names exactly the missing release keychain, G2 intermediate and notary profile and is recorded, and scripts/test-scripts.sh covers valid, missing-intermediate, expiring, mismatched, locked and unlocked cases from recorded tool output. Never prints a secret.

## Notes

2026-11-17: implemented in #509 (stack #512, bottom; head 6e4c2a138): scripts/check-signing.sh + signing-lib.sh + keychain-status.swift (prompts turned off before reading), make macos-signing-check, packaging/DeveloperIDG2CA.cer pinned (sha256 f16cd3c5...) and reviewed in SUPPLY-CHAIN-SECURITY.md, codesign --keychain via sign() in common.sh, notarize.sh --keychain with the profile, release.sh preflight runs the doctor --for-release. test-release-logic.sh covers valid, missing-intermediate, expiring (20/60 days), mismatched SIGN_IDENTITY and intermediate, locked, unlocked, and today's-build-Mac cases on Linux (make test) and macOS; test-scripts.sh runs the real reader and doctor against a throwaway keychain on CI only. Left in progress: (1) run make macos-signing-check on the build Mac before O1-O3 and record its report (expected: exactly the missing release keychain, G2 intermediate, and notary profile, and no prompt); (2) confirm the macOS CI job's throwaway-keychain checks pass on #509; (3) the README's signing-session checks 1-4.

2026-11-17: review A on #509 addressed in bb5e4cd73 and cd3e153a9 (head). macOS CI (run 44048368988) showed: after set-keychain-settings -l -u -t 600 macOS 26 reports use_lock_interval=0 lock_interval=600, and -l alone gives lock_interval=2147483647; the doctor now decides on lock_interval (0 < it <= release_keychain_lock_seconds). security create-keychain does not add the keychain to the user search list; the doctor's miss now prints the list-keychains -s command keeping existing entries, and CI ran it. A missed profile item is a warning unless ONLINE=1 or --for-release, where notarytool history decides. notary_credential_kind is shared with notarize.sh. Still open as before: the doctor's first run on the build Mac and the runbook's signing-session checks.

2026-11-17: #509 head 36b7281b4 (adds the is_developer_id_signed pipe fix); macOS CI green (runs 44048368988, 44052069029); dispositions posted: https://github.com/jlevy/metabrowser/pull/509#issuecomment-6944187158
