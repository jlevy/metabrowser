---
type: is
id: is-01kzyp7db8ewcb4nnpf4arhfpj
title: Add conserved semantic tallies to navigation and rollup APIs
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-semantic-file-type-families.md
labels:
  - file-types
  - inventory
  - api
dependencies:
  - type: blocks
    target: is-01kzyp7mj195jbenqsm6y8e2af
  - type: blocks
    target: is-01kzyp7vt7qe3e25d01w11db8g
parent_id: is-01kzyp6zfgt2xkj2wepzx6n5cq
created_at: 2026-08-13T23:09:57.991Z
updated_at: 2026-08-13T23:10:12.806Z
---
Refactor InventoryIndex.navigation_tallies to classify once per file and return typed raw, canonical, family, category, and recency tallies. Extend inventory_rollup.py and wire_models.py with family parents, bounded canonical children, raw type_top ranking, explicit No extension, and a final Remaining types tail. Add canonical_extensions, type_families, and type_tallies additively while retaining existing fields and proving child, family, and root conservation for tracked and ignored populations.
