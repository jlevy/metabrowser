---
type: is
id: is-01m7k2xdgr9b8sra4vrd372fe2
title: "macOS app: a release workflow that signs, notarizes and drafts a release from a macos-v tag"
kind: task
status: open
priority: 3
version: 6
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m748xzfj0nvstrsj9766877c
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:06:23.383Z
updated_at: 2026-11-16T23:48:09.392Z
---
Phase 2 of the publishing plan. Add .github/workflows/macos-release.yml, run only on push of macos-v* tags, with concurrency grouped by the tag's ref and cancel-in-progress: false (PR #485 A10). Job check: no environment, contents: read; validates the tag against apps/macos/VERSION and that its commit is on main, and ends the run when the tag's release already has assets. It catches mistakes only: it runs from the tagged commit's own workflow, which a hostile tag supplies (PR #485 B2). Job sign: needs check; environment macos-release (owner as required reviewer, approved only in the web UI after the owner confirms the waiting run's commit is RELEASE_COMMIT, no administrator bypass; PR #485 A1, B2), contents: read only, full clone, persist-credentials false, no Python or npm installs; imports CI's own Developer ID Application identity (O4; PR #485 B1) and the committed G2 intermediate with ci-keychain.sh, writes the API key to a 0600 file, runs the signing doctor and make macos-release, deletes keychain and key in an always() step, and uploads the image, checksum and notary logs as workflow artifacts. Job draft: needs sign, no Apple secrets, contents: write, id-token: write, attestations: write; attests the image with actions/attest and creates the draft release with --verify-tag --latest=false. Asset names come from the one function in common.sh (PR #485 A6). Actions pinned by full SHA and reviewed in SUPPLY-CHAIN-SECURITY.md. Confirm once that a tag created through gh api with the owner's token starts the workflow (refs created with GITHUB_TOKEN start none; PR #485 A2). Lands with or after mb-yqrs (PR #485 A22). Done when the first tag after the owner's CI setup produces a draft whose image passes make macos-check-release BUILT=ci.
