---
type: is
id: is-01m7k2w8wrwrypxm2vxyqaaa8v
title: "macOS app: a read-only signing doctor (make macos-signing-check)"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7k2xcrjxtgfe2mepxas1434
  - type: blocks
    target: is-01m7k2xdgr9b8sra4vrd372fe2
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:05:45.879Z
updated_at: 2026-11-16T21:06:23.383Z
---
Phase 1 of the publishing plan. Add apps/macos/scripts/check-signing.sh and make macos-signing-check: read-only checks that a valid Developer ID Application identity is on the keychain search list; its certificate's issuer and whether that intermediate is installed (naming Developer ID - G2 and Apple PKI when it is not); days to expiry (fail under 30, warn under 90); SIGN_IDENTITY matches when set; Xcode and notarytool versions; the notary profile or API key variables, and with ONLINE=1 a notarytool history call. Each miss names the owner step that fixes it. release.sh's preflight calls it. Done when it reports exactly the missing G2 intermediate and missing notary profile on today's build Mac, and scripts/test-scripts.sh covers valid, missing-intermediate, expiring and mismatched identities from recorded tool output. Never prints a secret.
