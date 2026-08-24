---
type: is
id: is-01m0ta9e0vjj5c5bv4sagrdqks
title: Give the synthetic serving corpus an independent Git boundary
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels:
  - performance
  - validation
dependencies: []
parent_id: is-01m0t9zsx9vhh3bzp96mqkaa4z
created_at: 2026-08-24T16:40:05.402Z
updated_at: 2026-08-24T16:50:29.877Z
closed_at: 2026-08-24T16:50:29.876Z
close_reason: Synthetic corpora now have a versioned independent Git boundary, old cached shapes rebuild, and benchmark correctness rejects falsely empty catalogs; tests and paired 100,000-file runs pass.
resolution: null
duplicate_of: null
---
build_corpus defaults under the repository's ignored .bench directory but lacks its own .git boundary, so every synthetic file is classified as gitignored and the complete Quick File catalog is empty. Add a versioned corpus shape with a minimal Git root, make cached old-shape corpora rebuild, record ignored/tracked intent, and require a settled nonempty catalog when the walker reports files.

## Notes

Versioned the synthetic corpus as shape 2 and create a minimal nested .git/HEAD boundary before files. Cached old shapes rebuild, corpus metadata records ignored_files=0, a unit test proves the boundary, and the settled benchmark rejects an empty catalog when the walker found files. Both 10,000- and 100,000-file runs now exercise nonempty catalog delivery.
