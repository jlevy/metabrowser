---
type: is
id: is-01kzyp7780p949f87ay1evwhnz
title: Define the shared semantic file type taxonomy and SDK
kind: feature
status: closed
priority: 2
version: 9
spec_path: docs/project/specs/done/plan-2026-08-13-semantic-file-type-families.md
labels:
  - file-types
  - design-system
  - sdk
dependencies:
  - type: blocks
    target: is-01kzyp7db8ewcb4nnpf4arhfpj
  - type: blocks
    target: is-01kzyp7mj195jbenqsm6y8e2af
  - type: blocks
    target: is-01kzyp7vt7qe3e25d01w11db8g
  - type: blocks
    target: is-01kzyp82r1hbkx870at8tgt0xk
parent_id: is-01kzyp6zfgt2xkj2wepzx6n5cq
created_at: 2026-08-13T23:09:51.743Z
updated_at: 2026-08-14T00:21:22.555Z
closed_at: 2026-08-14T00:17:58.995Z
close_reason: Implemented the validated server-owned taxonomy, injected strict browser runtime, public SDK facade, declarations, packaged asset loading, and Python-to-browser parity coverage.
---
Extend file_type_filters.py with validated category and family declarations, generated broad presets, canonical suffix matching, category matching, and distribution keys. Serialize the catalog through settings, add a strict file_type_taxonomy.js runtime, expose a read-only plugin SDK facade, update types and asset packaging, and add Python/Node parity tests. Required examples include JavaScript, TypeScript, CSS, YAML, and Python; ambiguous unknown extensions remain raw.
