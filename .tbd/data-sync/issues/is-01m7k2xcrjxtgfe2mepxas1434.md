---
type: is
id: is-01m7k2xcrjxtgfe2mepxas1434
title: "macOS app: the release runbook (owner setup, checks, test matrix, approvals)"
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:06:22.608Z
updated_at: 2026-11-16T21:06:22.608Z
---
Phase 1 of the publishing plan. Update apps/macos/README.md Building a Release with the owner-only steps (G2 intermediate, App Store Connect API key, notary profile, CI environment and secrets, repository settings, approvals, the downloaded-image launch), the signing doctor, the checks, Apple's test matrix (fresh, upgrade, duplicate, another account, moved and not moved), the notes template and the approval record. Add the app release to docs/publishing.md's checklist with one rule for how a macos-v tag is created. Record each new action's review in SUPPLY-CHAIN-SECURITY.md. No secret, Team ID or personal path. Done when make format and make lint-check pass and the owner follows it for the first release.
