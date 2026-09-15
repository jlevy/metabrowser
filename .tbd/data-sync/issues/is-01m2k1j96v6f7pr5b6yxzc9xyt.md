---
type: is
id: is-01m2k1j96v6f7pr5b6yxzc9xyt
title: "Hosted review Phase 0A.3: implement deterministic frontmatter artifact codec"
kind: task
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
  - stack:pr125
dependencies:
  - type: blocks
    target: is-01m2k1jazdf4m31f1vt80n858q
parent_id: is-01m10vgw6vhq82cd495kvhh9gf
created_at: 2026-09-15T17:24:20.824Z
updated_at: 2026-09-15T17:38:44.889Z
closed_at: 2026-09-15T17:38:44.889Z
close_reason: The formal stack scope and provider-reference authority are documented; closed provider-neutral ChangeRequest models and a deterministic frontmatter codec are implemented with focused Python tests for identity, lifecycle, relationships, portable values, explicit nulls, opaque Markdown, and byte-sensitive snapshot identity.
resolution: null
duplicate_of: null
---
Add artifacts.py with parse_frontmatter_artifact, serialize_frontmatter_artifact, and snapshot_identity. Use frontmatter-format for fenced Markdown while preserving explicit nulls, empty collections, Unicode, and the complete opaque Markdown body. Hash the exact deterministic UTF-8 artifact bytes. Keep filesystem publication, atomic rename, locks, and cache paths out of this helper. Add tests/test_hosted_review_artifacts.py first for body preservation, canonical byte stability, body-sensitive hashes, malformed fences, and proof that prose is never parsed for machine fields.
