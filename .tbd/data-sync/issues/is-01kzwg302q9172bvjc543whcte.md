---
type: is
id: is-01kzwg302q9172bvjc543whcte
title: Implement folder Overview panels and dual file-type summary
kind: epic
status: closed
priority: 1
version: 20
spec_path: docs/project/specs/done/plan-2026-08-12-directory-file-type-summary.md
labels:
  - folder-overview
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
child_order_hints:
  - is-01kzwkvevmw18dyvwjnxnyv58a
  - is-01kzwkvtqqrtdyafd6vkspsm9b
  - is-01kzwkw4ppv374t7ae849n5yvx
  - is-01kzwkwgrrdww56y99n5gsz65c
  - is-01kzwkwvt6ppnxg0m5snmps1eb
  - is-01kzwkx7fnx68rfsx0d6y36w1w
  - is-01kzwkxd4y4n9nmrjzv08etrpw
  - is-01kzwkxst27f1wrrq2ktft2jmy
  - is-01kzwky52tcet4twn7e4eknkje
  - is-01kzwkyd569xvj3ak0edyfv8pm
  - is-01kzwyse2ag672nwnasd2rvq38
  - is-01kzx0eym6ynrqvk9c6h2z1gn0
  - is-01kzy6th25xazbwyf8xqmn5j89
created_at: 2026-08-13T02:44:13.014Z
updated_at: 2026-08-13T18:40:47.172Z
closed_at: 2026-08-13T06:16:42.477Z
close_reason: All ten implementation beads are complete; Folder Overview, dual-metric File types, README composition, shared Treemap colors, documentation, packaging, browser review, and full validation are complete.
---
Implement the linked folder Overview contract: Overview is the default folder tab; Treemap remains a peer and future Files can be another peer. Add a public deterministic panel registry with independent availability, failure, print, and disposal boundaries. Register File types as the always-present summary panel, README as a conditional ordinary rendered-Markdown document panel, and prove extensibility with a synthetic third contribution. File types uses paired Files and Size distributions over one stable category/color set, exact count/byte rows, dual-metric bounded rollup ranking, honest partial and empty-folder states, and full browser lifecycle/accessibility coverage. Reconcile the WIP folder-view and rollup foundation before integration.

## Notes

Implemented all ten child scopes on codex/folder-overview-implementation. Folder Overview is the default directory view; File types and conditional README are modular panels; Treemap remains a peer tab. Real-browser review covered light/dark, wide/narrow, empty directories, navigation and reload persistence, shared colors, and a clean console. Final local gate: make verify with 953 passed, 1 skipped, CLI goldens, audits, distribution inspection, and installed-wheel smoke checks passing.
