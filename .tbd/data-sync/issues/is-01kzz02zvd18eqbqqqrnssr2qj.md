---
type: is
id: is-01kzz02zvd18eqbqqqrnssr2qj
title: Seed and reconcile the shared display taxonomy
kind: feature
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/done/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - registry
  - taxonomy
dependencies:
  - type: blocks
    target: is-01kzz039dpehjrvpg7nm2e47ft
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:02:18.847Z
updated_at: 2026-08-14T03:33:58.174Z
closed_at: 2026-08-14T02:26:39.238Z
close_reason: Moved the existing taxonomy into Registry v1 and added ordered Code, Documentation, Data, Logs, Archives, Media, and Other groups with conservative Log files, Archives, Images, Videos, Audio, and Fonts coverage; taxonomy and inventory tests pass.
---
Move every existing Metabrowser family into Registry v1 and reconcile major fdu kinds without importing fdu analyzer categories as UI groups. Add ordered Code, Docs, Data, Logs, Archives, Media, and Other groups; Log files, Archives, Images, Videos, Audio, and Fonts; and the required JSON Lines, SVG, C/C++, and singleton-family semantics. Keep the source conservative and leave ambiguous or uncommon formats under Remaining types. Tests: stable IDs/order, unique membership, expected content-family orthogonality, JSON versus JSON Lines, compound archives, media seeds, and parity with all previously supported filters. Acceptance: no extension membership is hand-maintained outside the registry.
