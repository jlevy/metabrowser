---
type: is
id: is-01kzz03kns6hp4a0rzkqnbjdww
title: Publish schemas, conformance corpus, and drift tooling
kind: feature
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - compatibility
  - testing
dependencies:
  - type: blocks
    target: is-01kzz03xc66nzafcd0dn48zger
  - type: blocks
    target: is-01kzz04fp7330jyn2h03m635qc
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:02:39.160Z
updated_at: 2026-08-14T02:48:42.470Z
closed_at: 2026-08-14T02:48:42.469Z
close_reason: Published validated v1 schemas, generated Python/browser conformance corpus, drift check, and self-contained revision-pinned export packet.
---
Add machine-readable schemas for file-type-registry-v1, file-type-breakdown-v1, and file-type-conformance-v1; normalized valid/invalid registry fixtures; exhaustive metadata cases; and conserved aggregate examples. Add Python and browser tests that consume the same corpus plus a checked sync/export command accepting an explicit destination or release artifact. Record schema version, registry revision, fingerprint, and source revision in the compatibility packet. Tests: every declaration, validation code, non-ASCII/native filename boundary where applicable, deterministic normalization, and browser/Python parity. Acceptance: a future fdu implementation can copy the packet and test Rust behavior without interpreting Metabrowser UI code.
