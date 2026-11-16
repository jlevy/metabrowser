---
type: is
id: is-01m7k5kbx9eb3ezaef642z3y8t
title: "PR #485 A3: Only CI-built releases have an attestation, but every release is required to pass the attestation check"
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-16-macos-app-publishing.md
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m7k1vctj6d370jg7hqdps4hk
hold: null
hold_until: null
created_at: 2026-11-16T21:53:19.784Z
updated_at: 2026-11-16T22:09:54.107Z
started_at: 2026-11-16T21:53:36.882Z
closed_at: 2026-11-16T22:09:54.106Z
close_reason: "Fixed in 83ef69fc3: build provenance attestation only for CI builds; mb-xd4o takes BUILT=local|ci, pins --signer-workflow and --source-ref, and prints which provenance it verified; a local build's provenance is the checksum, digest and gh release verify-asset; Goals restated."
resolution: null
duplicate_of: null
---
Medium. PLAN:54-55, :58-59, :449-455, :506, :516-517, :550. actions/attest needs an Actions OIDC token, so 0.1.0, built locally, has none. Fix: require the attestation only for CI-built releases and say which provenance was verified; a local release's provenance is the checksum, GitHub's digest and gh release verify-asset; never attest a local image from a workflow; verify with --signer-workflow and --source-ref. Review A (round 1) of PR #485: https://github.com/jlevy/metabrowser/pull/485#pullrequestreview-5928293258
