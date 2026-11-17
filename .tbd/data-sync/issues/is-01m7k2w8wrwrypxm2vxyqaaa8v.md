---
type: is
id: is-01m7k2w8wrwrypxm2vxyqaaa8v
title: "macOS app: a read-only signing doctor and the release keychain (make macos-signing-check)"
kind: task
status: in_progress
priority: 2
version: 6
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
updated_at: 2026-11-17T07:36:57.257Z
started_at: 2026-11-17T07:36:57.257Z
---
Phase 1 of the publishing plan; lands first, alone, and runs on the build Mac before the owner's O1-O3, so its report directs them (PR #485 A4). Add apps/macos/scripts/check-signing.sh and make macos-signing-check, read-only, never unlocking a keychain or prompting: a valid Developer ID Application identity in the release keychain SIGN_KEYCHAIN names (default ~/Library/Keychains/metabrowser-release.keychain-db), warning when one is also in the login keychain; that keychain on the search list, its lock settings, and whether it is unlocked now (PR #485 A1); the certificate's issuer and whether that intermediate is installed and matches the committed copy (naming Developer ID - G2 and Apple PKI when not); days to expiry (fail under 30, warn under 90); SIGN_IDENTITY matches when set; Xcode and notarytool versions; the notary profile in the release keychain or the API key variables, and with ONLINE=1 a notarytool history call. Each miss names the owner step that fixes it. Also: commit the G2 intermediate under apps/macos/packaging/ with its SHA-256 and a SUPPLY-CHAIN-SECURITY.md entry recording its source and that it chains to the system Apple Root CA (PR #485 A21); build-app.sh and make-dmg.sh pass codesign --keychain "$SIGN_KEYCHAIN", notarize.sh passes --keychain with the profile, and release.sh's preflight calls the doctor. Done when its report on today's build Mac names exactly the missing release keychain, G2 intermediate and notary profile and is recorded, and scripts/test-scripts.sh covers valid, missing-intermediate, expiring, mismatched, locked and unlocked cases from recorded tool output. Never prints a secret.
