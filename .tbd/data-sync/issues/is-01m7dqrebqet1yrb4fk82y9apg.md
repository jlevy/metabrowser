---
type: is
id: is-01m7dqrebqet1yrb4fk82y9apg
title: "Docs: design system cuts, development and e2e guides, rollup format"
kind: task
status: closed
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-14-documentation-from-first-principles.md
labels: []
dependencies: []
parent_id: is-01m7dqmdjvjrgqd3vpqw3z3zdc
created_at: 2026-11-14T19:15:13.910Z
updated_at: 2026-11-15T08:17:04.189Z
closed_at: 2026-11-15T08:17:04.188Z
close_reason: Implemented on claude/docs-first-principles (one standalone PR)
resolution: null
duplicate_of: null
---
Phase 2, PR 6: contributor documents.

- docs/design-system.md stays one file (about 2,800 lines). Cut replacement history (:765-770, :857-859, :878-880, :2484-2488, :3014, :3391), measurement narratives (:773-779, :3247-3251, :3269-3418) to explorations/ with one-line links, and the palette derivation (:2278-2509) to color_oklch.py docstrings. Merge its keyboard sections (Keyboard Keys, Main Tab Shortcuts, Pulls Keys, Keyboard Shortcuts and Commands) into one. Copy the rollup palette in from file-rollup-format/file-rollup-format.md :217-292 and delete it there.
- docs/development.md (about 500): delete asset loading tiers (copied by the plugins-and-browser PR), move durable storage and experiment-record rules (:961-1013) to explorations/performance-loop/README.md, inventory-provider development (:124-146) to arch-inventory-provider.md, rollup format maintenance (:408-462) to the format's directory. Gain the benchmark method from docs/engine-performance-model.md :72-170 (delete it there and trim that file to about 80 lines) and the parity rationale from arch-views-models-routes.md :746-864, merged with :618-688 (the map-and-entry PR deletes it in the map). Replace restatements of AGENTS.md with links. Fix: stale v0.12 alpha pointers (:97-102), spec phase language (:132, :144), the tbd cool-off contradiction (:932 against :480-484), and history (:210-212, :494, :694, :966-968). Point "the map" (:859-863) at docs/architecture.md. Update AGENTS.md links to moved anchors.
- docs/e2e-testing.md (about 420): manual browser recipes (:422-643) to a QA checklist under docs/project/qa/; the navigation performance playbook (:480-534) to explorations/performance-loop/; remove stale pointers (:414-419) and duplication with development.md (:72-87, :175-205).
