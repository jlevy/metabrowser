---
type: is
id: is-01m7k2xcrjxtgfe2mepxas1434
title: "macOS app: the release runbook (owner setup, checks, test matrix, approvals)"
kind: task
status: in_progress
priority: 2
version: 6
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@vm
labels: []
dependencies:
  - type: blocks
    target: is-01m748xzfj0nvstrsj9766877c
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:06:22.608Z
updated_at: 2026-11-17T08:17:10.142Z
started_at: 2026-11-17T07:58:06.489Z
---
Phase 1 of the publishing plan. Update apps/macos/README.md Building a Release with the owner-only steps O1-O9 (the release keychain with the identity imported -x and its .p12 kept offline, the G2 intermediate, the App Store Connect API key and notary profile, CI's own certificate, environment and secrets, repository settings, the cask after alpha feedback, approvals in order including the check that a waiting CI run's commit is RELEASE_COMMIT, the downloaded-image launch, publication with --latest=false, yearly renewal) and the leak step; the signing prompts a release brings (two for a local release) and the lock that can lapse during the notarization wait (PR #485 B9); the signing doctor, the checks, the test matrix (fresh, upgrade, duplicate, another account, moved and not moved) linked to the clean-account matrix mb-5fp7 rather than repeated (PR #485 A6), the notes template and the approval record. Add the app release to docs/publishing.md's release checklist; its macOS App Releases tag rule and Failure Handling landed with PR #485 (A2, A5, B5, B6). No secret, Team ID or personal path. Done when make format and make lint-check pass and the owner follows it for the first release.

## Notes

2026-11-17: implemented in #510 (head 170f9fae3): apps/macos/README.md Building a Release is the runbook (who does what, O1-O6 and O9 with checks, the leak step, each release in order with O7/O8, the two prompts and the idle-lock lapse, the checks table, the test matrix linked to the native plan's Phase 5 clean-account matrix, notes template, approval record, Checks Only a Signing Session Can Make); docs/publishing.md App Release Checklist and Q8; plan records Q6-Q8. make format and make lint-check pass; tests/test_macos_release_scripts.py pins O1's -t to release_keychain_lock_seconds. Left in progress: the owner follows it for the first release. Open for the owner: Q8 as relayed puts the tag after the SHA-256 and notes approval, while Release Flow creates it before the build and draft; the runbook follows Release Flow until the owner settles it.
