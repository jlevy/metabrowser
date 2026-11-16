---
type: is
id: is-01m7k2xdgr9b8sra4vrd372fe2
title: "macOS app: a release workflow that signs, notarizes and drafts a release from a macos-v tag"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7k2xe5286604ke24q8svdgq
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:06:23.383Z
updated_at: 2026-11-16T21:06:24.033Z
---
Phase 2 of the publishing plan. Add .github/workflows/macos-release.yml, run only on push of macos-v* tags. It refuses a tag that does not match apps/macos/VERSION or a commit not on main. Job sign: environment macos-release (required reviewer), contents: read only, full clone, persist-credentials false, no Python or npm installs; imports the identity with ci-keychain.sh, writes the API key to a 0600 file, runs the signing doctor and make macos-release, deletes keychain and key in an always() step, and uploads the image, checksum and notary logs as workflow artifacts. Job draft: needs sign, no Apple secrets, contents: write, id-token: write, attestations: write; attests the image with actions/attest and creates the draft release with --verify-tag --latest=false. Actions pinned by full SHA and reviewed. Done when the first tag after the owner's CI setup produces a draft whose image passes make macos-check-release and gh attestation verify.
