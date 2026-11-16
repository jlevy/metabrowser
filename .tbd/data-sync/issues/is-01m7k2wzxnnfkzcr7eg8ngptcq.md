---
type: is
id: is-01m7k2wzxnnfkzcr7eg8ngptcq
title: "macOS app: an ephemeral CI keychain script, rehearsed on every change"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7k2xdgr9b8sra4vrd372fe2
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
created_at: 2026-11-16T21:06:09.460Z
updated_at: 2026-11-16T21:06:23.383Z
---
Phase 2 of the publishing plan. Add apps/macos/scripts/ci-keychain.sh create|import|cleanup: a keychain in RUNNER_TEMP with a password generated in the job, the identity imported with -T /usr/bin/codesign and partition list apple-tool:,apple:,codesign:, the Developer ID G2 intermediate pinned by SHA-256 in the script, the keychain first on the user search list, and cleanup that deletes it and restores the list. macos-app.yml rehearses it with a throwaway self-signed identity on every change. Done when the rehearsal passes, find-identity lists the identity, and a forced import failure still runs cleanup.
