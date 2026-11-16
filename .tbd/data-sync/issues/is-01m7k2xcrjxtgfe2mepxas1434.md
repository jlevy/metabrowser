---
type: is
id: is-01m7k2xcrjxtgfe2mepxas1434
title: "macOS app: the release runbook (owner setup, checks, test matrix, approvals)"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xzfj0nvstrsj9766877c
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:06:22.608Z
updated_at: 2026-11-16T23:47:48.567Z
---
Phase 1 of the publishing plan. Update apps/macos/README.md Building a Release with the owner-only steps O1-O9 (the release keychain with the identity imported -x and its .p12 kept offline, the G2 intermediate, the App Store Connect API key and notary profile, CI's own certificate, environment and secrets, repository settings, the cask after alpha feedback, approvals in order including the check that a waiting CI run's commit is RELEASE_COMMIT, the downloaded-image launch, publication with --latest=false, yearly renewal) and the leak step; the signing prompts a release brings (two for a local release) and the lock that can lapse during the notarization wait (PR #485 B9); the signing doctor, the checks, the test matrix (fresh, upgrade, duplicate, another account, moved and not moved) linked to the clean-account matrix mb-5fp7 rather than repeated (PR #485 A6), the notes template and the approval record. Add the app release to docs/publishing.md's release checklist; its macOS App Releases tag rule and Failure Handling landed with PR #485 (A2, A5, B5, B6). No secret, Team ID or personal path. Done when make format and make lint-check pass and the owner follows it for the first release.
