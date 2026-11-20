---
type: is
id: is-01m7bbsczjpsn8sc1xpj7vbhad
title: "fdu: read File Rollup registry schema 5 (chroma_ratio) after #404"
kind: task
status: open
priority: 3
version: 5
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - upstream
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-13T21:07:33.489Z
updated_at: 2026-11-20T17:26:44.473Z
---
Follow-up from #404 (TypeScript yellow, mb-0avy): the File Rollup registry schema moved from 4 to 5 for the new optional `chroma_ratio` field (a per-family chroma share, 0 to 1, that requires a `deviation`).

fdu implements the same format: `crates/fdu-core/src/classify/file_rollup_manifest.rs` accepts `SCHEMA_VERSIONS: [3, 4]` and refuses others, so it will refuse a schema-5 registry, as the format's Evolution contract intends. fdu's vendored `rules/file-types.toml` is unaffected until it adopts schema 5.

Done when fdu reads schema 5, including `chroma_ratio`, in its own repository (not this one).

## Notes

Standalone: the work is in the fdu repository.
