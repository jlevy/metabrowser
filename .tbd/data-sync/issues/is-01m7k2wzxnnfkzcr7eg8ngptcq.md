---
type: is
id: is-01m7k2wzxnnfkzcr7eg8ngptcq
title: "macOS app: an ephemeral CI keychain script, rehearsed on every change"
kind: task
status: open
priority: 3
version: 6
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/485
    at: 2026-11-20T17:02:04.838Z
labels:
  - linear
dependencies:
  - type: blocks
    target: is-01m7k2xdgr9b8sra4vrd372fe2
parent_id: is-01m7hgpc9550w78kmwqsvv64xh
created_at: 2026-11-16T21:06:09.460Z
updated_at: 2026-11-20T17:24:51.671Z
---
Phase 2 of the publishing plan. Add apps/macos/scripts/ci-keychain.sh create|import|cleanup: a keychain in RUNNER_TEMP with a password generated in the job, the identity imported with -T /usr/bin/codesign and partition list apple-tool:,apple:,codesign:, the G2 intermediate imported from the copy committed under apps/macos/packaging/ so the job downloads nothing (PR #485 A21), the keychain first on the user search list, the API key written to a mode 0600 file in RUNNER_TEMP, and cleanup that deletes the keychain and the key and restores the list. The passwords reach security as arguments, as in GitHub's recipe, acceptable only on a runner discarded after the job; the script turns shell tracing off and never echoes them (PR #485 A9). macos-app.yml rehearses it with a throwaway self-signed identity on every change. Done when the rehearsal passes, find-identity lists the identity, and a forced import failure still runs cleanup.
